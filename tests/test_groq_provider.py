import json
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.llm.base import BaseLLMProvider
from app.llm.groq_provider import GroqProvider


def test_groq_provider_implements_base_interface():
    mock_client = MagicMock()
    provider = GroqProvider(api_key="gsk-test", client=mock_client)
    assert isinstance(provider, BaseLLMProvider)


@pytest.mark.anyio
async def test_groq_provider_parses_valid_json_response():
    expected_data = {
        "clean_title": "Amul Pure Ghee 1L Tin",
        "category": "Groceries",
        "brand": "Amul",
        "tags": ["ghee", "dairy", "cooking", "pure"],
    }

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(expected_data)
    mock_response.choices = [mock_choice]

    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    provider = GroqProvider(api_key="gsk-test", client=mock_client)
    result = await provider.enrich(
        raw_title="amul pure ghee 1l",
        raw_description="traditional clarified butter",
    )

    assert result == expected_data
    mock_client.chat.completions.create.assert_awaited_once()


@pytest.mark.anyio
async def test_groq_provider_raises_error_on_malformed_json():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Malformed {not json"
    mock_response.choices = [mock_choice]

    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    provider = GroqProvider(api_key="gsk-test", client=mock_client)
    with pytest.raises(ValueError, match="Failed to parse Groq LLM response as JSON"):
        await provider.enrich(raw_title="some title")


@pytest.mark.anyio
async def test_groq_provider_raises_error_on_empty_content():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = ""
    mock_response.choices = [mock_choice]

    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    provider = GroqProvider(api_key="gsk-test", client=mock_client)
    with pytest.raises(ValueError, match="Empty response received from Groq LLM provider"):
        await provider.enrich(raw_title="empty test")
