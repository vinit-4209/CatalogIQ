import asyncio
import logging
from typing import Any, Dict, Optional
from app.llm.base import BaseLLMProvider
from app.llm.validator import validate_enrichment
from app.services.llm_limiter import get_llm_semaphore
from app.services.metrics import metrics

logger = logging.getLogger(__name__)

DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_BASE_BACKOFF_S = 0.2


async def call_with_retries(
    provider: BaseLLMProvider,
    raw_title: str,
    raw_description: Optional[str] = None,
    semaphore: Optional[asyncio.Semaphore] = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_backoff_s: float = DEFAULT_BASE_BACKOFF_S,
) -> Dict[str, Any]:
    """
    Call provider.enrich() with output validation and exponential backoff retry.

    - Protects each individual LLM call with the shared semaphore.
    - Releases semaphore before sleeping during backoff.
    - Up to `max_attempts` total attempts (1 initial + 3 retries).
    - Backoff formula: base_backoff_s * (2 ** attempt).
    """
    if semaphore is None:
        semaphore = get_llm_semaphore()

    last_error: Optional[Exception] = None

    for attempt in range(max_attempts):
        try:
            # 1. Acquire semaphore ONLY for the duration of the LLM call
            async with semaphore:
                metrics.record_llm_call_started()
                try:
                    raw_result = await provider.enrich(
                        raw_title=raw_title,
                        raw_description=raw_description,
                    )
                except Exception:
                    metrics.record_llm_error()
                    raise
                finally:
                    metrics.record_llm_call_finished()

            # 2. Validate output outside the semaphore
            try:
                validated = validate_enrichment(raw_result)
                return validated
            except Exception:
                metrics.record_llm_error()
                raise

        except Exception as exc:
            last_error = exc
            is_final_attempt = attempt == max_attempts - 1
            if is_final_attempt:
                logger.warning(
                    "All %d LLM attempts failed for '%s'. Final error: %s",
                    max_attempts,
                    raw_title,
                    exc,
                )
                break

            backoff = base_backoff_s * (2**attempt)
            logger.info(
                "Attempt %d/%d failed for '%s' (%s). Retrying in %.3fs...",
                attempt + 1,
                max_attempts,
                raw_title,
                exc,
                backoff,
            )
            if backoff > 0:
                await asyncio.sleep(backoff)

    raise last_error if last_error else RuntimeError("LLM call failed with no exception")
