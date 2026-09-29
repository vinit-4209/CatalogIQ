import asyncio
from typing import Optional
from app.database import create_job, get_job, get_product, init_db
from app.llm.base import BaseLLMProvider
from app.schemas import ProductInput
from app.services.job_processor import process_job
from app.services.llm_limiter import reset_llm_semaphore


class ConcurrencyTrackingProvider(BaseLLMProvider):
    def __init__(self, delay_s: float = 0.05):
        self.delay_s = delay_s
        self.current_concurrency = 0
        self.max_observed_concurrency = 0
        self.total_calls = 0
        self.lock = asyncio.Lock()

    async def enrich(
        self, raw_title: str, raw_description: Optional[str] = None
    ) -> dict:
        async with self.lock:
            self.total_calls += 1
            self.current_concurrency += 1
            if self.current_concurrency > self.max_observed_concurrency:
                self.max_observed_concurrency = self.current_concurrency

        try:
            await asyncio.sleep(self.delay_s)
        finally:
            async with self.lock:
                self.current_concurrency -= 1

        return {
            "clean_title": raw_title.strip().title(),
            "category": "Electronics",
            "brand": "TechCorp",
            "tags": ["tech", "gadget"],
        }


def test_global_llm_concurrency_limit(tmp_path):
    test_db = tmp_path / "test_concurrency.db"
    init_db(test_db)

    # 1. Configure concurrency limit to 2 for the test
    shared_semaphore = reset_llm_semaphore(concurrency=2)

    # 2. Setup tracking provider
    provider = ConcurrencyTrackingProvider(delay_s=0.05)

    # 3. Create 3 jobs with 3 products each (9 products total)
    jobs_data = []
    for job_idx in range(1, 4):
        job_id = f"job_concurrent_{job_idx}"
        products = [
            ProductInput(
                sku=f"SKU-J{job_idx}-P{p_idx}",
                raw_title=f"Electronic Gadget {job_idx}-{p_idx}",
            )
            for p_idx in range(1, 4)
        ]
        create_job(job_id=job_id, total=len(products), db_path=test_db)
        jobs_data.append((job_id, products))

    # 4. Run all 3 jobs concurrently with asyncio.gather
    async def run_all_jobs():
        await asyncio.gather(
            *(
                process_job(
                    job_id=j_id,
                    products=prods,
                    provider=provider,
                    db_path=test_db,
                    semaphore=shared_semaphore,
                )
                for j_id, prods in jobs_data
            )
        )

    asyncio.run(run_all_jobs())

    # 5. Assert concurrency constraints
    assert provider.max_observed_concurrency <= 2
    assert provider.max_observed_concurrency == 2
    assert provider.total_calls == 9

    # 6. Verify all jobs and products completed successfully
    for j_id, prods in jobs_data:
        job = get_job(j_id, db_path=test_db)
        assert job is not None
        assert job["status"] == "completed"
        assert job["total"] == 3
        assert job["done"] == 3
        assert job["failed"] == 0

        for p in prods:
            prod_row = get_product(p.sku, db_path=test_db)
            assert prod_row is not None
            assert prod_row["status"] == "enriched"
            assert prod_row["clean_title"] == p.raw_title.strip().title()
            assert prod_row["category"] == "Electronics"
            assert prod_row["brand"] == "TechCorp"
            assert prod_row["error"] is None
