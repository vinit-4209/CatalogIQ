import pytest
from pydantic import ValidationError
from app.schemas import (
    ProductInput,
    JobCreateRequest,
    ProductUpdateRequest,
    VALID_CATEGORIES,
)


def test_valid_product_input():
    prod = ProductInput(
        sku="SKU-123",
        raw_title="Amul Butter 500g",
        raw_description="Dairy pack",
    )
    assert prod.sku == "SKU-123"
    assert prod.raw_title == "Amul Butter 500g"
    assert prod.raw_description == "Dairy pack"

    # Optional description can be omitted
    prod_no_desc = ProductInput(sku="SKU-124", raw_title="Amul Milk")
    assert prod_no_desc.raw_description is None


def test_empty_sku_rejected():
    with pytest.raises(ValidationError):
        ProductInput(sku="", raw_title="Valid Title")

    with pytest.raises(ValidationError):
        ProductInput(sku="   ", raw_title="Valid Title")


def test_empty_raw_title_rejected():
    with pytest.raises(ValidationError):
        ProductInput(sku="SKU-123", raw_title="")

    with pytest.raises(ValidationError):
        ProductInput(sku="SKU-123", raw_title="   ")


def test_empty_products_list_rejected():
    with pytest.raises(ValidationError):
        JobCreateRequest(products=[])


def test_valid_category_accepted():
    for cat in VALID_CATEGORIES:
        req = ProductUpdateRequest(category=cat)
        assert req.category == cat


def test_invalid_category_rejected():
    with pytest.raises(ValidationError):
        ProductUpdateRequest(category="NonExistentCategory")


def test_empty_clean_title_rejected():
    with pytest.raises(ValidationError):
        ProductUpdateRequest(clean_title="")

    with pytest.raises(ValidationError):
        ProductUpdateRequest(clean_title="   ")


def test_valid_product_update_request():
    req = ProductUpdateRequest(
        clean_title="Amul Butter 500 g",
        category="Groceries",
        tags=["butter", "dairy"],
    )
    assert req.clean_title == "Amul Butter 500 g"
    assert req.category == "Groceries"
    assert req.tags == ["butter", "dairy"]

    # Omitting fields is valid
    empty_req = ProductUpdateRequest()
    assert empty_req.clean_title is None
    assert empty_req.category is None
    assert empty_req.tags is None
