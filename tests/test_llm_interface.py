import asyncio
import pytest
from app.llm.base import BaseLLMProvider


class DummyProvider(BaseLLMProvider):
    async def enrich(
        self, raw_title: str, raw_description: str | None = None
    ) -> dict:
        return {
            "clean_title": raw_title.strip().title(),
            "category": "Groceries",
            "brand": "DummyBrand",
            "tags": ["test"],
        }


def test_abstract_base_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseLLMProvider()


def test_concrete_provider_implements_interface():
    provider = DummyProvider()
    result = asyncio.run(provider.enrich("amul butter 500g", "pack of 2"))

    assert isinstance(result, dict)
    assert result["clean_title"] == "Amul Butter 500G"
    assert result["category"] == "Groceries"
    assert result["brand"] == "DummyBrand"
    assert result["tags"] == ["test"]
