import json
import logging
from pathlib import Path
from typing import List, Optional, Union

from app.database import (
    DEFAULT_DB_PATH,
    increment_job_counter,
    mark_job_completed,
    mark_job_running,
    upsert_product,
)
from app.llm.base import BaseLLMProvider
from app.llm.mock import MockLLMProvider
from app.llm.validator import validate_enrichment
from app.schemas import ProductInput

logger = logging.getLogger(__name__)


async def process_job(
    job_id: str,
    products: List[ProductInput],
    provider: Optional[BaseLLMProvider] = None,
    db_path: Union[Path, str] = DEFAULT_DB_PATH,
) -> None:
    """
    Process products for a job asynchronously in the background.

    - Updates job status to 'running'.
    - Processes each product with LLM enrichment and validation.
    - Saves individual product results to SQLite.
    - Updates job progress counters (done / failed).
    - Updates job status to 'completed' upon completion.
    """
    if provider is None:
        provider = MockLLMProvider()

    # 1. Mark the job as running
    mark_job_running(job_id, db_path=db_path)

    # 2. Process products sequentially
    for product in products:
        try:
            raw_result = await provider.enrich(
                raw_title=product.raw_title,
                raw_description=product.raw_description,
            )
            validated = validate_enrichment(raw_result)

            upsert_product(
                {
                    "sku": product.sku,
                    "raw_title": product.raw_title,
                    "raw_description": product.raw_description,
                    "clean_title": validated["clean_title"],
                    "category": validated["category"],
                    "brand": validated["brand"],
                    "tags": json.dumps(validated["tags"]),
                    "status": "enriched",
                    "error": None,
                    "content_hash": None,
                },
                db_path=db_path,
            )
            increment_job_counter(job_id, "done", db_path=db_path)

        except Exception as exc:
            logger.warning("Product enrichment failed for SKU %s: %s", product.sku, exc)
            upsert_product(
                {
                    "sku": product.sku,
                    "raw_title": product.raw_title,
                    "raw_description": product.raw_description,
                    "clean_title": None,
                    "category": None,
                    "brand": None,
                    "tags": None,
                    "status": "failed",
                    "error": str(exc),
                    "content_hash": None,
                },
                db_path=db_path,
            )
            increment_job_counter(job_id, "failed", db_path=db_path)

    # 3. Mark the job as completed
    mark_job_completed(job_id, db_path=db_path)
