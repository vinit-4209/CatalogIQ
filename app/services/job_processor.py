import asyncio
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
from app.schemas import ProductInput
from app.services.dedup import calculate_content_hash, get_or_enrich_product
from app.services.llm_limiter import get_llm_semaphore
from app.services.retry import DEFAULT_BASE_BACKOFF_S

logger = logging.getLogger(__name__)


async def _process_single_product(
    product: ProductInput,
    job_id: str,
    provider: BaseLLMProvider,
    db_path: Union[Path, str],
    semaphore: asyncio.Semaphore,
    base_backoff_s: float = DEFAULT_BASE_BACKOFF_S,
) -> None:
    """Process a single product using deduplication, retries, and semaphore protection."""
    content_hash = calculate_content_hash(
        raw_title=product.raw_title,
        raw_description=product.raw_description,
    )

    try:
        validated, is_cache_hit = await get_or_enrich_product(
            raw_title=product.raw_title,
            raw_description=product.raw_description,
            content_hash=content_hash,
            provider=provider,
            db_path=db_path,
            semaphore=semaphore,
            base_backoff_s=base_backoff_s,
        )

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
                "content_hash": content_hash,
            },
            db_path=db_path,
        )
        if is_cache_hit:
            increment_job_counter(job_id, "cache_hits", db_path=db_path)
        increment_job_counter(job_id, "done", db_path=db_path)

    except Exception as exc:
        logger.warning(
            "Product enrichment failed for SKU %s: %s",
            product.sku,
            exc,
        )
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
                "content_hash": content_hash,
            },
            db_path=db_path,
        )
        increment_job_counter(job_id, "failed", db_path=db_path)


async def process_job(
    job_id: str,
    products: List[ProductInput],
    provider: Optional[BaseLLMProvider] = None,
    db_path: Union[Path, str] = DEFAULT_DB_PATH,
    semaphore: Optional[asyncio.Semaphore] = None,
    base_backoff_s: float = DEFAULT_BASE_BACKOFF_S,
) -> None:
    """
    Process products for a job asynchronously in the background.

    - Updates job status to 'running'.
    - Performs content-based deduplication and in-flight duplicate waiting.
    - Limits concurrent LLM calls with process-wide semaphore and exponential backoff.
    - Saves individual product results and content_hash to SQLite.
    - Updates job progress counters (done / failed / cache_hits).
    - Updates job status to 'completed' upon completion.
    """
    if provider is None:
        provider = MockLLMProvider()

    if semaphore is None:
        semaphore = get_llm_semaphore()

    # 1. Mark the job as running
    mark_job_running(job_id, db_path=db_path)

    # 2. Process products bounded by the shared semaphore with retries and dedup
    await asyncio.gather(
        *(
            _process_single_product(
                product=product,
                job_id=job_id,
                provider=provider,
                db_path=db_path,
                semaphore=semaphore,
                base_backoff_s=base_backoff_s,
            )
            for product in products
        )
    )

    # 3. Mark the job as completed
    mark_job_completed(job_id, db_path=db_path)
