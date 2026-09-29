from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseLLMProvider(ABC):
    """Abstract base class defining the interface for LLM providers."""

    @abstractmethod
    async def enrich(
        self,
        raw_title: str,
        raw_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Enrich a product listing into structured catalog data.

        Returns:
            dict containing clean_title, category, brand, and tags.
        """
        pass
