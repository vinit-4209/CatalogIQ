import asyncio
from typing import Optional
from app.config import settings

_llm_semaphore: Optional[asyncio.Semaphore] = None


def get_llm_semaphore(concurrency: Optional[int] = None) -> asyncio.Semaphore:
    """
    Get or initialize the process-wide LLM concurrency semaphore.
    Defaults to settings.llm_concurrency.
    """
    global _llm_semaphore
    if _llm_semaphore is None:
        limit = concurrency if concurrency is not None else settings.llm_concurrency
        _llm_semaphore = asyncio.Semaphore(limit)
    return _llm_semaphore


def reset_llm_semaphore(concurrency: Optional[int] = None) -> asyncio.Semaphore:
    """
    Reset and return the process-wide LLM semaphore with a specified concurrency limit.
    Primarily used for testing or dynamic reconfiguration.
    """
    global _llm_semaphore
    limit = concurrency if concurrency is not None else settings.llm_concurrency
    _llm_semaphore = asyncio.Semaphore(limit)
    return _llm_semaphore
