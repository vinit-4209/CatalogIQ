from typing import Any, Dict
from app.schemas import VALID_CATEGORIES


def validate_enrichment(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate LLM enrichment output.

    Raises ValueError if required fields are missing or invalid.
    Returns the validated dictionary.
    """
    if not isinstance(result, dict):
        raise ValueError("Enrichment output must be a dictionary")

    # 1. clean_title
    if "clean_title" not in result:
        raise ValueError("Missing required field: 'clean_title'")
    clean_title = result["clean_title"]
    if not isinstance(clean_title, str) or not clean_title.strip():
        raise ValueError("'clean_title' must be a non-empty string")

    # 2. category
    if "category" not in result:
        raise ValueError("Missing required field: 'category'")
    category = result["category"]
    if not isinstance(category, str) or category not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category '{category}'. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
        )

    # 3. brand
    if "brand" not in result:
        raise ValueError("Missing required field: 'brand'")
    brand = result["brand"]
    if brand is not None and not isinstance(brand, str):
        raise ValueError("'brand' must be a string or None")

    # 4. tags
    if "tags" not in result:
        raise ValueError("Missing required field: 'tags'")
    tags = result["tags"]
    if not isinstance(tags, list):
        raise ValueError("'tags' must be a list")
    if len(tags) > 5:
        raise ValueError(f"'tags' cannot have more than 5 items, got {len(tags)}")
    for i, tag in enumerate(tags):
        if not isinstance(tag, str):
            raise ValueError(f"Tag at index {i} must be a string, got {type(tag).__name__}")
        if tag != tag.lower():
            raise ValueError(f"Tag '{tag}' must be lowercase")

    return result
