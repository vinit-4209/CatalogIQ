import asyncio
from typing import Optional
from app.database import create_job, get_job, get_product, init_db
from app.llm.base import BaseLLMProvider
from app.schemas import ProductInput
from app.services.dedup import calculate_content_hash, normalize_content
from app.services.job_processor import process_job


class CallCountingProvider(BaseLLMProvider):
    def __init__(self, delay_s: float = 0.0):
        self.delay_s = delay_s
        self.call_count = 0
        self.lock = asyncio.Lock()

    async def enrich(
        self, raw_title: str, raw_description: Optional[str] = None
    ) -> dict:
        async with self.lock:
            self.call_count += 1

        if self.delay_s > 0:
            await asyncio.sleep(self.delay_s)

        return {
            "clean_title": raw_title.strip().title(),
            "category": "Groceries",
            "brand": "Amul",
            "tags": ["butter", "dairy"],
        }


class FailOnceThenSucceedProvider(BaseLLMProvider):
    def __init__(self):
        self.should_fail = True
        self.call_count = 0
        self.lock = asyncio.Lock()

    async def enrich(
        self, raw_title: str, raw_description: Optional[str] = None
    ) -> dict:
        async with self.lock:
            self.call_count += 1
            fail = self.should_fail

        if fail:
            raise RuntimeError("Initial simulated failure")

        return {
            "clean_title": raw_title.strip().title(),
            "category": "Groceries",
            "brand": "Amul",
            "tags": ["butter"],
        }


def test_normalization_and_content_hash():
    # Different casing, whitespace, and tabs should produce the exact same normalized content & hash
    t1, d1 = "  AMUL   Butter 500G \t", " Pack   of   2  "
    t2, d2 = "amul butter 500g", "pack of 2"

    norm1 = normalize_content(t1, d1)
    norm2 = normalize_content(t2, d2)
    assert norm1 == "amul butter 500g pack of 2"
    assert norm1 == norm2

    hash1 = calculate_content_hash(t1, d1)
    hash2 = calculate_content_hash(t2, d2)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex string


def test_sequential_duplicate_caching(tmp_path):
    test_db = tmp_path / "test_dedup_seq.db"
    init_db(test_db)

    provider = CallCountingProvider()

    # 1. Process Product A in Job 1
    prod_a = [
        ProductInput(
            sku="SKU-A",
            raw_title="  Amul butter 500G",
            raw_description="pack of 2",
        )
    ]
    create_job("job_1", total=1, db_path=test_db)
    asyncio.run(process_job("job_1", prod_a, provider=provider, db_path=test_db))

    assert provider.call_count == 1
    job1 = get_job("job_1", db_path=test_db)
    assert job1["done"] == 1
    assert job1["cache_hits"] == 0

    # 2. Process Product B with identical normalized content in Job 2
    prod_b = [
        ProductInput(
            sku="SKU-B",
            raw_title="AMUL BUTTER 500g   ",
            raw_description="  pack   of 2 ",
        )
    ]
    create_job("job_2", total=1, db_path=test_db)
    asyncio.run(process_job("job_2", prod_b, provider=provider, db_path=test_db))

    # Assert provider was NOT called again
    assert provider.call_count == 1

    # Product B reused enriched data
    b_record = get_product("SKU-B", db_path=test_db)
    assert b_record is not None
    assert b_record["status"] == "enriched"
    assert b_record["clean_title"] == "Amul Butter 500G"
    assert b_record["category"] == "Groceries"
    assert b_record["brand"] == "Amul"

    # Assert job 2 recorded a cache hit
    job2 = get_job("job_2", db_path=test_db)
    assert job2["status"] == "completed"
    assert job2["done"] == 1
    assert job2["cache_hits"] == 1


def test_simultaneous_duplicate_in_flight(tmp_path):
    test_db = tmp_path / "test_dedup_simultaneous.db"
    init_db(test_db)

    # Provider that sleeps so both jobs run concurrently while the first is in-flight
    provider = CallCountingProvider(delay_s=0.05)

    prod1 = [
        ProductInput(
            sku="SKU-SIM-1",
            raw_title="Amul Butter 500g",
            raw_description="Pack of 2",
        )
    ]
    prod2 = [
        ProductInput(
            sku="SKU-SIM-2",
            raw_title="AMUL BUTTER 500G",
            raw_description="pack of 2",
        )
    ]
    prod3 = [
        ProductInput(
            sku="SKU-SIM-3",
            raw_title="  amul  butter  500g ",
            raw_description=" pack of 2 ",
        )
    ]

    create_job("job_sim_1", total=1, db_path=test_db)
    create_job("job_sim_2", total=1, db_path=test_db)
    create_job("job_sim_3", total=1, db_path=test_db)

    async def run_simultaneous():
        await asyncio.gather(
            process_job("job_sim_1", prod1, provider=provider, db_path=test_db),
            process_job("job_sim_2", prod2, provider=provider, db_path=test_db),
            process_job("job_sim_3", prod3, provider=provider, db_path=test_db),
        )

    asyncio.run(run_simultaneous())

    # Only ONE LLM call was executed across all 3 concurrent jobs
    assert provider.call_count == 1

    # All 3 products are enriched
    for sku in ("SKU-SIM-1", "SKU-SIM-2", "SKU-SIM-3"):
        p = get_product(sku, db_path=test_db)
        assert p is not None
        assert p["status"] == "enriched"
        assert p["clean_title"] == "Amul Butter 500G"

    # Job 1 was owner, Job 2 and 3 received cache hits
    j1 = get_job("job_sim_1", db_path=test_db)
    j2 = get_job("job_sim_2", db_path=test_db)
    j3 = get_job("job_sim_3", db_path=test_db)

    assert j1["status"] == "completed" and j1["done"] == 1
    assert j2["status"] == "completed" and j2["done"] == 1
    assert j3["status"] == "completed" and j3["done"] == 1

    total_cache_hits = j1["cache_hits"] + j2["cache_hits"] + j3["cache_hits"]
    assert total_cache_hits == 2


def test_failed_enrichment_is_not_cached(tmp_path):
    test_db = tmp_path / "test_dedup_failed_not_cached.db"
    init_db(test_db)

    provider = FailOnceThenSucceedProvider()

    # 1. First job fails all 4 retries
    prod_fail = [ProductInput(sku="SKU-F", raw_title="Amul Butter 500g")]
    create_job("job_f", total=1, db_path=test_db)
    asyncio.run(
        process_job(
            "job_f",
            prod_fail,
            provider=provider,
            db_path=test_db,
            base_backoff_s=0.001,
        )
    )

    assert provider.call_count == 4
    prod_f_row = get_product("SKU-F", db_path=test_db)
    assert prod_f_row["status"] == "failed"

    # 2. Switch provider to succeeding mode
    provider.should_fail = False

    # 3. Second job submits identical product
    prod_succeed = [ProductInput(sku="SKU-S", raw_title="Amul Butter 500g")]
    create_job("job_s", total=1, db_path=test_db)
    asyncio.run(
        process_job(
            "job_s",
            prod_succeed,
            provider=provider,
            db_path=test_db,
            base_backoff_s=0.001,
        )
    )

    # Provider was called again (call_count was 4, now 5)
    assert provider.call_count == 5

    # Second product succeeded (not reused failure)
    prod_s_row = get_product("SKU-S", db_path=test_db)
    assert prod_s_row["status"] == "enriched"
    assert prod_s_row["clean_title"] == "Amul Butter 500G"


def test_non_duplicate_distinct_products_call_provider(tmp_path):
    test_db = tmp_path / "test_non_duplicates.db"
    init_db(test_db)

    provider = CallCountingProvider()
    products = [
        ProductInput(sku="SKU-D1", raw_title="Product One"),
        ProductInput(sku="SKU-D2", raw_title="Product Two"),
        ProductInput(sku="SKU-D3", raw_title="Product Three"),
    ]
    create_job("job_distinct", total=3, db_path=test_db)
    asyncio.run(
        process_job("job_distinct", products, provider=provider, db_path=test_db)
    )

    assert provider.call_count == 3
    job = get_job("job_distinct", db_path=test_db)
    assert job["done"] == 3
    assert job["cache_hits"] == 0
