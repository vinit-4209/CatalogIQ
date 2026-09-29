from typing import List, Optional
from pydantic import BaseModel, ConfigDict, field_validator

VALID_CATEGORIES = {
    "Groceries",
    "Beverages",
    "Personal Care",
    "Household",
    "Electronics",
    "Fashion",
    "Home & Kitchen",
    "Other",
}


class ProductInput(BaseModel):
    sku: str
    raw_title: str
    raw_description: Optional[str] = None

    @field_validator("sku", "raw_title")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field must not be empty")
        return v


class JobCreateRequest(BaseModel):
    products: List[ProductInput]

    @field_validator("products")
    @classmethod
    def validate_products(cls, v: List[ProductInput]) -> List[ProductInput]:
        if not v:
            raise ValueError("products list must not be empty")
        return v


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    total: int
    done: int
    failed: int
    cache_hits: int
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku: str
    raw_title: str
    raw_description: Optional[str] = None
    clean_title: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    tags: Optional[List[str]] = None
    status: str
    error: Optional[str] = None


class ProductUpdateRequest(BaseModel):
    clean_title: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None

    @field_validator("clean_title")
    @classmethod
    def validate_clean_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("clean_title must not be empty")
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_CATEGORIES:
            raise ValueError(
                f"category must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
            )
        return v


class ProductListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: List[ProductResponse]
    page: int
    page_size: int
    total: int
