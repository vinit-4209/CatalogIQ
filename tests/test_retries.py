import asyncio
from typing import Optional
from app.database import create_job, get_job, get_product, init_db
from app.llm.base import BaseLLMProvider
from app.schemas import ProductInput
from app.services.job_processor import process_job
from app.services.llm_limiter import reset_llm_semaphore


class FlakyProvider(BaseLLMProvider):
    """Provider that fails a fixed number of times before succeeding."""

    def __init__(self, failures_before_success: int):
        self.failures_before_success = failures_before_success
        self.call_count = 0
        self.lock = asyncio.Lock()

    async def enrich(
        self, raw_title: str, raw_description: Optional[str] = None
    ) -> dict:
        async with self.lock:
            self.call_count += 1
            current_call = self.call_count

        if current_call <= self.failures_before_success:
            raise RuntimeError(f"Simulated network error on attempt {current_call}")

        return {
            "clean_title": raw_title.strip().title(),
            "category": "Groceries",
            "brand": "Amul",
            "tags": ["butter", "dairy"],
        }


class AlwaysFailingProvider(BaseLLMProvider):
    """Provider that always fails."""

    def __init__(self):
        self.call_count = 0
        self.lock = asyncio.Lock()

    async def enrich(
        self, raw_title: str, raw_description: Optional[str] = None
    ) -> dict:
        async with self.lock:
            self.call_count += 1
        raise RuntimeError("Persistent LLM API outage")


class InvalidOutputThenValidProvider(BaseLLMProvider):
    """Provider that returns invalid schema first, then valid schema."""

    def __init__(self):
        self.call_count = 0
        self.lock = asyncio.Lock()

    async def enrich(
        self, raw_title: str, raw_description: Optional[str] = None
    ) -> dict:
        async with self.lock:
            self.call_count += 1
            current_call = self.call_count

        if current_call == 1:
            # Missing clean_title and invalid category
            return {
                "category": "InvalidCategoryName",
                "brand": "Unknown",
                "tags": ["invalid"],
            }

        return {
            "clean_title": raw_title.strip().title(),
            "category": "Groceries",
            "brand": "Amul",
            "tags": ["butter"],
        }


class ConcurrencyAndRetryTrackingProvider(BaseLLMProvider):
    """Provider that simulates retries and tracks concurrent in-flight calls."""

    def __init__(self, delay_s: float = 0.02):
        self.delay_s = delay_s
        self.call_count = 0
        self.current_concurrency = 0
        self.max_observed_concurrency = 0
        self.lock = asyncio.Lock()

    async def enrich(
        self, raw_title: str, raw_description: Optional[str] = None
    ) -> dict:
        async with self.lock:
            self.call_count += 1
            self.current_concurrency += 1
            if self.current_concurrency > self.max_observed_concurrency:
                self.max_observed_concurrency = self.current_concurrency
            call_num = self.call_count

        try:
            await asyncio.sleep(self.delay_s)
            # Fail every first attempt per product to force retries
            if "retry_me" in raw_title and call_num % 2 == 1:
                raise RuntimeError("Simulated transient failure")
        finally:
            async with self.lock:
                self.current_concurrency -= 1

        return {
            "clean_title": raw_title.strip().title(),
            "category": "Groceries",
            "brand": "Amul",
            "tags": ["butter"],
        }


def test_retry_eventually_succeeds(tmp_path):
    test_db = tmp_path / "test_retry_success.db"
    init_db(test_db)

    provider = FlakyProvider(failures_before_success=2)
    products = [ProductInput(sku="SKU-RETRY-1", raw_title="Amul Butter 500g")]
    create_job("job_retry_success", total=1, db_path=test_db)

    asyncio.run(
        process_job(
            job_id="job_retry_success",
            products=products,
            provider=provider,
            db_path=test_db,
            base_backoff_s=0.001,
        )
    )

    # 1. Exactly 3 attempts made (2 failed + 1 successful)
    assert provider.call_count == 3

    # 2. Product is enriched
    prod = get_product("SKU-RETRY-1", db_path=test_db)
    assert prod is not None
    assert prod["status"] == "enriched"
    assert prod["clean_title"] == "Amul Butter 500G"
    assert prod["error"] is None

    # 3. Job counts
    job = get_job("job_retry_success", db_path=test_db)
    assert job is not None
    assert job["status"] == "completed"
    assert job["done"] == 1
    assert job["failed"] == 0


def test_all_retries_fail_marks_product_failed(tmp_path):
    test_db = tmp_path / "test_retry_failure.db"
    init_db(test_db)

    provider = AlwaysFailingProvider()
    products = [ProductInput(sku="SKU-FAIL-1", raw_title="Failing Item")]
    create_job("job_retry_fail", total=1, db_path=test_db)

    asyncio.run(
        process_job(
            job_id="job_retry_fail",
            products=products,
            provider=provider,
            db_path=test_db,
            base_backoff_s=0.001,
        )
    )

    # Exactly 4 total attempts made (1 initial + 3 retries, no 5th attempt)
    assert provider.call_count == 4

    # Product status is failed with the error message
    prod = get_product("SKU-FAIL-1", db_path=test_db)
    assert prod is not None
    assert prod["status"] == "failed"
    assert "Persistent LLM API outage" in prod["error"]

    # Job counts
    job = get_job("job_retry_fail", db_path=test_db)
    assert job is not None
    assert job["status"] == "completed"
    assert job["done"] == 0
    assert job["failed"] == 1


def test_invalid_llm_output_is_retried(tmp_path):
    test_db = tmp_path / "test_invalid_output.db"
    init_db(test_db)

    provider = InvalidOutputThenValidProvider()
    products = [ProductInput(sku="SKU-INVALID-1", raw_title="Amul Butter")]
    create_job("job_invalid_retry", total=1, db_path=test_db)

    asyncio.run(
        process_job(
            job_id="job_invalid_retry",
            products=products,
            provider=provider,
            db_path=test_db,
            base_backoff_s=0.001,
        )
    )

    # First call failed validation, second call passed
    assert provider.call_count == 2

    prod = get_product("SKU-INVALID-1", db_path=test_db)
    assert prod is not None
    assert prod["status"] == "enriched"
    assert prod["clean_title"] == "Amul Butter"
    assert prod["category"] == "Groceries"


def test_retry_preserves_global_concurrency_limit(tmp_path):
    test_db = tmp_path / "test_retry_concurrency.db"
    init_db(test_db)

    # Configure concurrency limit to 2
    shared_semaphore = reset_llm_semaphore(concurrency=2)
    provider = ConcurrencyAndRetryTrackingProvider(delay_s=0.03)

    products = [
        ProductInput(sku=f"SKU-C-{i}", raw_title=f"retry_me item {i}")
        for i in range(4)
    ]
    create_job("job_retry_conc", total=len(products), db_path=test_db)

    asyncio.run(
        process_job(
            job_id="job_retry_conc",
            products=products,
            provider=provider,
            db_path=test_db,
            semaphore=shared_semaphore,
            base_backoff_s=0.001,
        )
    )

    # Concurrency never exceeded 2 even while retrying
    assert provider.max_observed_concurrency <= 2
    assert provider.max_observed_concurrency == 2

    job = get_job("job_retry_conc", db_path=test_db)
    assert job["status"] == "completed"
    assert job["done"] == 4
    assert job["failed"] == 0
