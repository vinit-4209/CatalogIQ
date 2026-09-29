import json
import logging
import os
from typing import Any, Optional

from dotenv import load_dotenv

from app.config import settings
from app.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

ENRICHMENT_SYSTEM_PROMPT = (
    "You are an e-commerce catalog enrichment assistant.\n"
    "Given a raw product title and optional raw description, extract and generate structured catalog attributes.\n\n"
    "Output MUST be a valid JSON object with the following fields:\n"
    '- "clean_title": A clean, readable, standardized product title without promotional fluff or typos.\n'
    '- "category": Exactly one of: ["Groceries", "Beverages", "Personal Care", "Household", "Electronics", "Fashion", "Home & Kitchen", "Other"]\n'
    '- "brand": The inferred brand name as a string, or null if unknown or unbranded.\n'
    '- "tags": A list of up to 5 lowercase keyword tags describing the product.\n\n'
    "Respond ONLY with valid JSON."
)


class GroqProvider(BaseLLMProvider):
    """
    Groq LLM provider implementing BaseLLMProvider using the official groq SDK.
    Provides fast, free tier inference via Groq Cloud API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        client: Any = None,
    ):
        load_dotenv(override=True)
        self.api_key = api_key or os.getenv("GROQ_API_KEY") or settings.groq_api_key
        self.model = (
            model
            or os.getenv("GROQ_MODEL")
            or os.getenv("LLM_MODEL")
            or settings.groq_model
            or "openai/gpt-oss-120b"
        )

        if client is not None:
            self._client = client
        else:
            if not self.api_key:
                raise ValueError(
                    "GROQ_API_KEY environment variable is required when using GroqProvider."
                )
            from groq import AsyncGroq

            self._client = AsyncGroq(api_key=self.api_key)

    async def enrich(
        self,
        raw_title: str,
        raw_description: Optional[str] = None,
    ) -> dict:
        user_content = f"Raw Title: {raw_title}"
        if raw_description:
            user_content += f"\nRaw Description: {raw_description}"

        response = await self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": ENRICHMENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response received from Groq LLM provider")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Failed to parse Groq LLM response as JSON: {exc}"
            ) from exc

        if not isinstance(parsed, dict):
            raise ValueError(
                f"LLM output must be a JSON object, got: {type(parsed).__name__}"
            )

        return parsed
