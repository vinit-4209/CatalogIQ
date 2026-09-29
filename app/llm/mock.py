import asyncio
import random
import re
from typing import Any, Dict, List, Optional
from app.config import settings
from app.llm.base import BaseLLMProvider

CATEGORY_KEYWORDS = {
    "Beverages": [
        "pepsi", "coke", "coca-cola", "juice", "water", "beverage", "soda", "drink", "tea", "coffee"
    ],
    "Groceries": [
        "butter", "milk", "rice", "bread", "grocery", "cheese", "flour", "sugar", "salt", "oil", "dal"
    ],
    "Personal Care": [
        "shampoo", "soap", "cream", "lotion", "toothpaste", "perfume", "deodorant", "serum"
    ],
    "Household": [
        "detergent", "cleaner", "bleach", "dishwash", "sponge", "wipe", "mop"
    ],
    "Electronics": [
        "phone", "laptop", "mouse", "keyboard", "monitor", "headphone", "earphone", "charger", "cable"
    ],
    "Fashion": [
        "shirt", "jeans", "shoes", "dress", "jacket", "pants", "tshirt", "t-shirt", "sneakers"
    ],
    "Home & Kitchen": [
        "kitchen", "pan", "plate", "knife", "pot", "cookware", "blender", "fork", "spoon", "bowl"
    ],
}

KNOWN_BRANDS = {
    "amul": "Amul",
    "nestle": "Nestle",
    "pepsi": "Pepsi",
    "coke": "Coca-Cola",
    "coca-cola": "Coca-Cola",
    "apple": "Apple",
    "samsung": "Samsung",
    "sony": "Sony",
    "nike": "Nike",
    "adidas": "Adidas",
    "dell": "Dell",
    "hp": "HP",
    "colgate": "Colgate",
    "dove": "Dove",
    "tide": "Tide",
}

STOP_WORDS = {
    "a", "an", "the", "and", "or", "of", "in", "for", "with", "pack", "pck", "pc", "g", "gm", "kg", "ml", "l"
}


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider simulating latency, random failures, and deterministic enrichment."""

    def __init__(
        self,
        latency_ms: Optional[int] = None,
        failure_rate: Optional[float] = None,
    ):
        self.latency_ms = (
            latency_ms if latency_ms is not None else settings.mock_latency_ms
        )
        self.failure_rate = (
            failure_rate if failure_rate is not None else settings.mock_failure_rate
        )

    async def enrich(
        self,
        raw_title: str,
        raw_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Simulate LLM enrichment with configured latency and failure rate."""
        # 1. Simulate latency
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)

        # 2. Simulate random failure
        if self.failure_rate > 0 and random.random() < self.failure_rate:
            raise RuntimeError(
                f"Mock LLM failed with simulated failure rate {self.failure_rate}"
            )

        # 3. Clean and normalize content
        combined_text = f"{raw_title} {raw_description or ''}".lower()

        # Category determination
        category = "Other"
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(re.search(rf"\b{re.escape(kw)}\b", combined_text) for kw in keywords):
                category = cat
                break

        # Brand detection
        brand = None
        for brand_key, brand_name in KNOWN_BRANDS.items():
            if re.search(rf"\b{re.escape(brand_key)}\b", combined_text):
                brand = brand_name
                break

        # Clean title: normalize spaces and convert to title case
        cleaned_words = [w.strip() for w in raw_title.strip().split() if w.strip()]
        clean_title = " ".join(cleaned_words).title()

        # Tags extraction: up to 5 lowercase unique words
        words = re.findall(r"[a-z0-9]+", combined_text)
        tags: List[str] = []
        for word in words:
            if word not in STOP_WORDS and len(word) > 2 and word not in tags:
                tags.append(word)
                if len(tags) == 5:
                    break

        return {
            "clean_title": clean_title,
            "category": category,
            "brand": brand,
            "tags": tags,
        }
