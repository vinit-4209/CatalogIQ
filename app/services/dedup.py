import asyncio
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from app.database import (
    DEFAULT_DB_PATH,
    get_enriched_product_by_content_hash,
)
from app.llm.base import BaseLLMProvider
from app.services.retry import DEFAULT_BASE_BACKOFF_S, call_with_retries

logger = logging.getLogger(__name__)

# Registry of in-flight enrichment futures: content_hash -> asyncio.Future
_in_flight: Dict[str, asyncio.Future] = {}
_in_flight_lock = asyncio.Lock()


def normalize_content(raw_title: str, raw_description: Optional[str] = None) -> str:
    """
    Normalize content by concatenating raw_title + ' ' + raw_description,
    lowercasing, and collapsing all repeated whitespace to a single space.
    """
    combined = f"{raw_title} {raw_description or ''}".lower()
    return " ".join(combined.split())


def calculate_content_hash(
    raw_title: str, raw_description: Optional[str] = None
) -> str:
    """Compute deterministic SHA-256 hash of normalized content."""
    normalized = normalize_content(raw_title, raw_description)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def get_or_enrich_product(
    raw_title: str,
    raw_description: Optional[str],
    content_hash: str,
    provider: BaseLLMProvider,
    db_path: Union[Path, str] = DEFAULT_DB_PATH,
    semaphore: Optional[asyncio.Semaphore] = None,
    base_backoff_s: float = DEFAULT_BASE_BACKOFF_S,
) -> Tuple[Dict[str, Any], bool]:
    """
    Check cache, await in-flight duplicate, or execute LLM enrichment with retries.

    Returns:
        (enrichment_dict, is_cache_hit: bool)
    """
    # 1. Check database for an existing successfully enriched product
    cached = get_enriched_product_by_content_hash(content_hash, db_path=db_path)
    if cached is not None:
        tags = cached["tags"]
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except Exception:
                tags = []
        return {
            "clean_title": cached["clean_title"],
            "category": cached["category"],
            "brand": cached["brand"],
            "tags": tags,
        }, True

    # 2. Check or register in-flight future
    async with _in_flight_lock:
        if content_hash in _in_flight:
            fut = _in_flight[content_hash]
            is_owner = False
        else:
            loop = asyncio.get_running_loop()
            fut = loop.create_future()
            _in_flight[content_hash] = fut
            is_owner = True

    # 3. If listener, await owner's result without holding the semaphore
    if not is_owner:
        result = await fut
        return result, True

    # 4. If owner, perform LLM enrichment with retries
    try:
        validated = await call_with_retries(
            provider=provider,
            raw_title=raw_title,
            raw_description=raw_description,
            semaphore=semaphore,
            base_backoff_s=base_backoff_s,
        )
        if not fut.done():
            fut.set_result(validated)
        return validated, False

    except Exception as exc:
        if not fut.done():
            fut.set_exception(exc)
        raise

    finally:
        async with _in_flight_lock:
            _in_flight.pop(content_hash, None)
