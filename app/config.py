import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()


def _get_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _get_float(key: str, default: float) -> float:
    val = os.getenv(key)
    if not val:
        return default
    try:
        return float(val)
    except ValueError:
        return default


from typing import Optional


@dataclass
class Settings:
    llm_provider: str = "mock"
    llm_concurrency: int = 5
    mock_latency_ms: int = 200
    mock_failure_rate: float = 0.1
    llm_model: Optional[str] = None
    groq_api_key: Optional[str] = None
    groq_model: str = "openai/gpt-oss-120b"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(override=True)
        llm_model = os.getenv("LLM_MODEL")
        return cls(
            llm_provider=os.getenv("LLM_PROVIDER") or "mock",
            llm_concurrency=_get_int("LLM_CONCURRENCY", 5),
            mock_latency_ms=_get_int("MOCK_LATENCY_MS", 200),
            mock_failure_rate=_get_float("MOCK_FAILURE_RATE", 0.1),
            llm_model=llm_model,
            groq_api_key=os.getenv("GROQ_API_KEY"),
            groq_model=os.getenv("GROQ_MODEL") or llm_model or "openai/gpt-oss-120b",
        )


settings = Settings.from_env()
