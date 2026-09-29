import asyncio
import time
import pytest
from app.llm.mock import MockLLMProvider
from app.schemas import VALID_CATEGORIES


def test_successful_enrichment_fields():
    provider = MockLLMProvider(latency_ms=0, failure_rate=0.0)
    result = asyncio.run(
        provider.enrich("AMUL butter 500G", "pck of 2")
    )

    assert isinstance(result, dict)
    assert "clean_title" in result
    assert "category" in result
    assert "brand" in result
    assert "tags" in result

    assert result["clean_title"] == "Amul Butter 500G"
    assert result["category"] == "Groceries"
    assert result["brand"] == "Amul"
    assert isinstance(result["tags"], list)


def test_returned_category_is_valid():
    provider = MockLLMProvider(latency_ms=0, failure_rate=0.0)
    test_cases = [
        ("Amul butter 500g", "Groceries"),
        ("Cold Pepsi can 300ml", "Beverages"),
        ("Dove moisture shampoo", "Personal Care"),
        ("Tide laundry detergent", "Household"),
        ("Apple wireless mouse", "Electronics"),
        ("Nike running shoes", "Fashion"),
        ("Non-stick frying pan", "Home & Kitchen"),
        ("Unknown strange gadget xyz", "Other"),
    ]

    for title, expected_category in test_cases:
        result = asyncio.run(provider.enrich(title))
        assert result["category"] in VALID_CATEGORIES
        assert result["category"] == expected_category


def test_tags_are_lowercase_and_max_five():
    provider = MockLLMProvider(latency_ms=0, failure_rate=0.0)
    result = asyncio.run(
        provider.enrich(
            "Organic whole grain brown rice delicious kitchen staple",
            "healthy nutritious premium grain selection",
        )
    )

    tags = result["tags"]
    assert isinstance(tags, list)
    assert len(tags) <= 5
    for tag in tags:
        assert tag == tag.lower()


def test_latency_respected():
    latency_ms = 60
    provider = MockLLMProvider(latency_ms=latency_ms, failure_rate=0.0)

    start = time.perf_counter()
    asyncio.run(provider.enrich("Test product"))
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms >= latency_ms * 0.85


def test_failure_rate_one_causes_failure():
    provider = MockLLMProvider(latency_ms=0, failure_rate=1.0)
    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(provider.enrich("Test product"))

    assert "simulated failure" in str(exc_info.value).lower()
