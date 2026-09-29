import asyncio
from typing import Optional
from app.database import create_job, get_job, init_db
from app.llm.base import BaseLLMProvider
from app.schemas import ProductInput
from app.services.job_processor import process_job
from app.services.llm_limiter import reset_llm_semaphore
from app.services.metrics import get_metrics, reset_metrics


class ImmediateSuccessProvider(BaseLLMProvider):
    async def enrich(
        self, raw_title: str, raw_description: Optional[str] = None
    ) -> dict:
        return {
            "clean_title": raw_title.strip().title(),
            "category": "Groceries",
            "brand": "Amul",
            "tags": ["butter"],
        }


class FlakyTwiceProvider(BaseLLMProvider):
    def __init__(self):
        self.count = 0
        self.lock = asyncio.Lock()

    async def enrich(
        self, raw_title: str, raw_description: Optional[str] = None
    ) -> dict:
        async with self.lock:
            self.count += 1
            call_idx = self.count

        if call_idx <= 2:
            raise RuntimeError("Transient provider glitch")

        return {
            "clean_title": raw_title.strip().title(),
            "category": "Groceries",
            "brand": "Amul",
            "tags": ["butter"],
        }


class InvalidOnceProvider(BaseLLMProvider):
    def __init__(self):
        self.count = 0
        self.lock = asyncio.Lock()

    async def enrich(
        self, raw_title: str, raw_description: Optional[str] = None
    ) -> dict:
        async with self.lock:
            self.count += 1
            call_idx = self.count

        if call_idx == 1:
            return {"category": "BadCategory", "brand": None, "tags": []}

        return {
            "clean_title": raw_title.strip().title(),
            "category": "Groceries",
            "brand": "Amul",
            "tags": ["butter"],
        }


class AlwaysFailingProvider(BaseLLMProvider):
    async def enrich(
        self, raw_title: str, raw_description: Optional[str] = None
    ) -> dict:
        raise RuntimeError("Service unavailable")


class DelaySuccessProvider(BaseLLMProvider):
    def __init__(self, delay_s: float = 0.05):
        self.delay_s = delay_s

    async def enrich(
        self, raw_title: str, raw_description: Optional[str] = None
    ) -> dict:
        await asyncio.sleep(self.delay_s)
        return {
            "clean_title": raw_title.strip().title(),
            "category": "Electronics",
            "brand": "Sony",
            "tags": ["audio"],
        }


def test_metrics_successful_call(tmp_path):
    reset_metrics()
    test_db = tmp_path / "test_metrics_success.db"
    init_db(test_db)

    products = [ProductInput(sku="SKU-1", raw_title="Amul Butter 500g")]
    create_job("job_1", 1, db_path=test_db)
    asyncio.run(
        process_job(
            "job_1",
            products,
            provider=ImmediateSuccessProvider(),
            db_path=test_db,
        )
    )

    m = get_metrics()
    assert m["total_llm_calls"] == 1
    assert m["llm_errors"] == 0
    assert m["max_concurrent_llm_calls"] == 1


def test_metrics_retry(tmp_path):
    reset_metrics()
    test_db = tmp_path / "test_metrics_retry.db"
    init_db(test_db)

    products = [ProductInput(sku="SKU-1", raw_title="Amul Butter 500g")]
    create_job("job_1", 1, db_path=test_db)
    asyncio.run(
        process_job(
            "job_1",
            products,
            provider=FlakyTwiceProvider(),
            db_path=test_db,
            base_backoff_s=0.001,
        )
    )

    m = get_metrics()
    assert m["total_llm_calls"] == 3
    assert m["llm_errors"] == 2


def test_metrics_validation_error(tmp_path):
    reset_metrics()
    test_db = tmp_path / "test_metrics_val.db"
    init_db(test_db)

    products = [ProductInput(sku="SKU-1", raw_title="Amul Butter 500g")]
    create_job("job_1", 1, db_path=test_db)
    asyncio.run(
        process_job(
            "job_1",
            products,
            provider=InvalidOnceProvider(),
            db_path=test_db,
            base_backoff_s=0.001,
        )
    )

    m = get_metrics()
    assert m["total_llm_calls"] == 2
    assert m["llm_errors"] == 1


def test_metrics_exhausted_retries(tmp_path):
    reset_metrics()
    test_db = tmp_path / "test_metrics_fail.db"
    init_db(test_db)

    products = [ProductInput(sku="SKU-1", raw_title="Failing Item")]
    create_job("job_1", 1, db_path=test_db)
    asyncio.run(
        process_job(
            "job_1",
            products,
            provider=AlwaysFailingProvider(),
            db_path=test_db,
            base_backoff_s=0.001,
        )
    )

    m = get_metrics()
    assert m["total_llm_calls"] == 4
    assert m["llm_errors"] == 4


def test_metrics_concurrency(tmp_path):
    reset_metrics()
    test_db = tmp_path / "test_metrics_conc.db"
    init_db(test_db)

    shared_semaphore = reset_llm_semaphore(concurrency=2)
    provider = DelaySuccessProvider(delay_s=0.05)

    products = [
        ProductInput(sku=f"SKU-{i}", raw_title=f"Distinct Item {i}")
        for i in range(4)
    ]
    create_job("job_conc", len(products), db_path=test_db)

    asyncio.run(
        process_job(
            "job_conc",
            products,
            provider=provider,
            db_path=test_db,
            semaphore=shared_semaphore,
        )
    )

    m = get_metrics()
    assert m["max_concurrent_llm_calls"] <= 2
    assert m["max_concurrent_llm_calls"] == 2
    assert m["total_llm_calls"] == 4
    assert m["llm_errors"] == 0


def test_metrics_dedup_sequential(tmp_path):
    reset_metrics()
    test_db = tmp_path / "test_metrics_dedup.db"
    init_db(test_db)

    provider = ImmediateSuccessProvider()

    # Product 1
    create_job("job_1", 1, db_path=test_db)
    asyncio.run(
        process_job(
            "job_1",
            [ProductInput(sku="SKU-1", raw_title="Amul Butter 500g")],
            provider=provider,
            db_path=test_db,
        )
    )

    # Product 2 (same content, different SKU)
    create_job("job_2", 1, db_path=test_db)
    asyncio.run(
        process_job(
            "job_2",
            [ProductInput(sku="SKU-2", raw_title="AMUL BUTTER 500G")],
            provider=provider,
            db_path=test_db,
        )
    )

    m = get_metrics()
    assert m["total_llm_calls"] == 1
    assert m["llm_errors"] == 0

    job2 = get_job("job_2", db_path=test_db)
    assert job2["cache_hits"] == 1
    assert job2["done"] == 1


def test_metrics_in_flight_duplicate(tmp_path):
    reset_metrics()
    test_db = tmp_path / "test_metrics_inflight.db"
    init_db(test_db)

    provider = DelaySuccessProvider(delay_s=0.05)

    prod1 = [ProductInput(sku="SKU-1", raw_title="Amul Butter 500g")]
    prod2 = [ProductInput(sku="SKU-2", raw_title="amul butter 500g")]

    create_job("job_1", 1, db_path=test_db)
    create_job("job_2", 1, db_path=test_db)

    async def run_both():
        await asyncio.gather(
            process_job("job_1", prod1, provider=provider, db_path=test_db),
            process_job("job_2", prod2, provider=provider, db_path=test_db),
        )

    asyncio.run(run_both())

    m = get_metrics()
    assert m["total_llm_calls"] == 1
    assert m["llm_errors"] == 0
