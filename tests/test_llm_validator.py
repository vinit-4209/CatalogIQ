import pytest
from app.llm.validator import validate_enrichment


def test_valid_output_passes():
    valid_data = {
        "clean_title": "Amul Butter 500g",
        "category": "Groceries",
        "brand": "Amul",
        "tags": ["butter", "dairy"],
    }
    validated = validate_enrichment(valid_data)
    assert validated == valid_data


def test_missing_clean_title_fails():
    data = {
        "category": "Groceries",
        "brand": "Amul",
        "tags": ["butter"],
    }
    with pytest.raises(ValueError, match="Missing required field: 'clean_title'"):
        validate_enrichment(data)


def test_empty_clean_title_fails():
    data_empty = {
        "clean_title": "",
        "category": "Groceries",
        "brand": "Amul",
        "tags": ["butter"],
    }
    with pytest.raises(ValueError, match="'clean_title' must be a non-empty string"):
        validate_enrichment(data_empty)

    data_whitespace = {
        "clean_title": "   ",
        "category": "Groceries",
        "brand": "Amul",
        "tags": ["butter"],
    }
    with pytest.raises(ValueError, match="'clean_title' must be a non-empty string"):
        validate_enrichment(data_whitespace)


def test_invalid_category_fails():
    data = {
        "clean_title": "Amul Butter 500g",
        "category": "InvalidCategory",
        "brand": "Amul",
        "tags": ["butter"],
    }
    with pytest.raises(ValueError, match="Invalid category"):
        validate_enrichment(data)


def test_missing_category_fails():
    data = {
        "clean_title": "Amul Butter 500g",
        "brand": "Amul",
        "tags": ["butter"],
    }
    with pytest.raises(ValueError, match="Missing required field: 'category'"):
        validate_enrichment(data)


def test_brand_none_passes():
    data = {
        "clean_title": "Generic Butter 500g",
        "category": "Groceries",
        "brand": None,
        "tags": ["butter"],
    }
    validated = validate_enrichment(data)
    assert validated["brand"] is None


def test_invalid_brand_type_fails():
    data = {
        "clean_title": "Amul Butter 500g",
        "category": "Groceries",
        "brand": 12345,
        "tags": ["butter"],
    }
    with pytest.raises(ValueError, match="'brand' must be a string or None"):
        validate_enrichment(data)


def test_more_than_five_tags_fails():
    data = {
        "clean_title": "Amul Butter 500g",
        "category": "Groceries",
        "brand": "Amul",
        "tags": ["butter", "dairy", "spread", "pasteurized", "salted", "extra"],
    }
    with pytest.raises(ValueError, match="cannot have more than 5 items"):
        validate_enrichment(data)


def test_non_list_tags_fails():
    data = {
        "clean_title": "Amul Butter 500g",
        "category": "Groceries",
        "brand": "Amul",
        "tags": "butter, dairy",
    }
    with pytest.raises(ValueError, match="'tags' must be a list"):
        validate_enrichment(data)


def test_uppercase_tag_fails():
    data = {
        "clean_title": "Amul Butter 500g",
        "category": "Groceries",
        "brand": "Amul",
        "tags": ["Butter"],
    }
    with pytest.raises(ValueError, match="must be lowercase"):
        validate_enrichment(data)
