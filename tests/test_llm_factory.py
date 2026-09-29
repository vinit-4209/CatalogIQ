import pytest

from app.config import settings
from app.llm.base import BaseLLMProvider
from app.llm.factory import get_llm_provider
from app.llm.groq_provider import GroqProvider
from app.llm.mock import MockLLMProvider


def test_factory_default_mock(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "mock")
    provider = get_llm_provider()
    assert isinstance(provider, MockLLMProvider)
    assert isinstance(provider, BaseLLMProvider)


def test_factory_groq_mode(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "gsk_test_key_12345")
    provider = get_llm_provider("groq")
    assert isinstance(provider, GroqProvider)
    assert isinstance(provider, BaseLLMProvider)


def test_factory_unsupported_provider():
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        get_llm_provider("unsupported_fake_model")
