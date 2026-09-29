import os
from typing import Optional
from dotenv import load_dotenv

from app.config import settings
from app.llm.base import BaseLLMProvider
from app.llm.mock import MockLLMProvider


def get_llm_provider(provider_name: Optional[str] = None) -> BaseLLMProvider:
    """
    Factory function returning the configured LLM provider instance.

    Supported values:
      - 'mock': MockLLMProvider (default, offline deterministic/simulated)
      - 'groq': GroqProvider (free high-speed inference)
    """
    name = (provider_name or settings.llm_provider).strip().lower()

    if name == "mock":
        return MockLLMProvider()

    if name == "groq":
        from app.llm.groq_provider import GroqProvider

        return GroqProvider()

    raise ValueError(
        f"Unsupported LLM provider: '{name}'. Supported providers: 'mock', 'groq'."
    )
