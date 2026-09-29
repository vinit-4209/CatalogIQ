import asyncio
import json
from app.database import (
    create_job,
    get_job,
    get_product,
    init_db,
)
from app.llm.base import BaseLLMProvider
from app.llm.mock import MockLLMProvider
from app.schemas import ProductInput
from app.services.job_processor import process_job


def test_successful_job_processing(tmp_path):
    test_db = tmp_path / "test_catalogiq.db"
    init_db(test_db)

    products = [
        ProductInput(
            sku="SKU-1",
            raw_title="Amul Butter 500g",
            raw_description="Pack of 2",
        ),
        ProductInput(
            sku="SKU-2",
            raw_title="Pepsi Can 300ml",
            raw_description=None,
        ),
    ]

    create_job("job_success", total=len(products), db_path=test_db)
    provider = MockLLMProvider(latency_ms=0, failure_rate=0.0)

    asyncio.run(
        process_job(
            job_id="job_success",
            products=products,
            provider=provider,
            db_path=test_db,
        )
    )

    job = get_job("job_success", db_path=test_db)
    assert job is not None
    assert job["status"] == "completed"
    assert job["total"] == 2
    assert job["done"] == 2
    assert job["failed"] == 0
    assert job["started_at"] is not None
    assert job["finished_at"] is not None

    prod1 = get_product("SKU-1", db_path=test_db)
    assert prod1 is not None
    assert prod1["status"] == "enriched"
    assert prod1["clean_title"] == "Amul Butter 500G"
    assert prod1["category"] == "Groceries"
    assert prod1["brand"] == "Amul"
    assert "butter" in json.loads(prod1["tags"])
    assert prod1["error"] is None

    prod2 = get_product("SKU-2", db_path=test_db)
    assert prod2 is not None
    assert prod2["status"] == "enriched"
    assert prod2["clean_title"] == "Pepsi Can 300Ml"
    assert prod2["category"] == "Beverages"
    assert prod2["brand"] == "Pepsi"
    assert prod2["error"] is None


class SelectiveFailureProvider(BaseLLMProvider):
    async def enrich(
        self, raw_title: str, raw_description: str | None = None
    ) -> dict:
        if "fail" in raw_title.lower():
            raise RuntimeError("Simulated failure for bad product")
        return {
            "clean_title": raw_title.title(),
            "category": "Groceries",
            "brand": "Amul",
            "tags": ["item"],
        }


def test_failed_product_does_not_stop_remaining_job(tmp_path):
    test_db = tmp_path / "test_catalogiq.db"
    init_db(test_db)

    products = [
        ProductInput(sku="SKU-1", raw_title="Good Product 1"),
        ProductInput(sku="SKU-2", raw_title="Fail Product 2"),
        ProductInput(sku="SKU-3", raw_title="Good Product 3"),
    ]

    create_job("job_partial", total=len(products), db_path=test_db)
    provider = SelectiveFailureProvider()

    asyncio.run(
        process_job(
            job_id="job_partial",
            products=products,
            provider=provider,
            db_path=test_db,
        )
    )

    job = get_job("job_partial", db_path=test_db)
    assert job is not None
    assert job["status"] == "completed"
    assert job["total"] == 3
    assert job["done"] == 2
    assert job["failed"] == 1

    prod1 = get_product("SKU-1", db_path=test_db)
    assert prod1["status"] == "enriched"
    assert prod1["error"] is None

    prod2 = get_product("SKU-2", db_path=test_db)
    assert prod2["status"] == "failed"
    assert "Simulated failure" in prod2["error"]

    prod3 = get_product("SKU-3", db_path=test_db)
    assert prod3["status"] == "enriched"
    assert prod3["error"] is None
