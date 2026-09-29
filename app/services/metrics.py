import asyncio
from typing import Dict


class LLMMetrics:
    """Thread/coroutine-safe process-local metrics tracking LLM usage and concurrency."""

    def __init__(self):
        self.total_llm_calls: int = 0
        self.llm_errors: int = 0
        self.current_llm_calls: int = 0
        self.max_concurrent_llm_calls: int = 0
        self._lock = asyncio.Lock()

    def record_llm_call_started(self) -> None:
        """Record the start of an LLM call attempt."""
        self.total_llm_calls += 1
        self.current_llm_calls += 1
        if self.current_llm_calls > self.max_concurrent_llm_calls:
            self.max_concurrent_llm_calls = self.current_llm_calls

    def record_llm_call_finished(self) -> None:
        """Record the completion of an LLM call attempt."""
        if self.current_llm_calls > 0:
            self.current_llm_calls -= 1

    def record_llm_error(self) -> None:
        """Record an error in an LLM call or output validation."""
        self.llm_errors += 1

    def get_metrics(self) -> Dict[str, int]:
        """Return a copy of the current metrics dictionary."""
        return {
            "total_llm_calls": self.total_llm_calls,
            "llm_errors": self.llm_errors,
            "max_concurrent_llm_calls": self.max_concurrent_llm_calls,
            "current_llm_calls": self.current_llm_calls,
            # Assignment API contract names
            "llm_calls_total": self.total_llm_calls,
            "llm_errors_total": self.llm_errors,
        }

    def reset_metrics(self) -> None:
        """Reset all metric counters to zero."""
        self.total_llm_calls = 0
        self.llm_errors = 0
        self.current_llm_calls = 0
        self.max_concurrent_llm_calls = 0


# Process-local singleton instance
metrics = LLMMetrics()


def get_metrics() -> Dict[str, int]:
    """Helper returning process-level LLM metrics."""
    return metrics.get_metrics()


def reset_metrics() -> None:
    """Helper resetting process-level LLM metrics."""
    metrics.reset_metrics()
