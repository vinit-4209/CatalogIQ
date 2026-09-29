import json
import uuid
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from app.config import settings
from app.database import (
    create_job,
    get_job,
    get_product,
    list_products,
    update_product_approval,
)
from app.schemas import (
    JobCreateRequest,
    ProductUpdateRequest,
)
from app.services.job_processor import process_job
from app.services.metrics import get_metrics

router = APIRouter(prefix="/api")


def format_product(row: dict) -> dict:
    """Format product row from SQLite for JSON response."""
    item = dict(row)
    tags = item.get("tags")
    if isinstance(tags, str):
        try:
            item["tags"] = json.loads(tags)
        except Exception:
            item["tags"] = []
    elif tags is None:
        item["tags"] = None
    return item


@router.get("/health")
def health_check():
    """Health check endpoint returning system status and LLM configuration."""
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "llm_concurrency": settings.llm_concurrency,
        "provider": settings.llm_provider,
        "concurrency": settings.llm_concurrency,
    }


@router.get("/metrics")
def get_metrics_endpoint():
    """Return runtime LLM counters and concurrency high-water mark."""
    m = get_metrics()
    return {
        "llm_calls_total": m["llm_calls_total"],
        "llm_errors_total": m["llm_errors_total"],
        "max_concurrent_llm_calls": m["max_concurrent_llm_calls"],
    }


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_job_endpoint(
    payload: JobCreateRequest,
    background_tasks: BackgroundTasks,
):
    """
    Submit a batch of products for enrichment.
    Returns HTTP 202 immediately with the job object and runs enrichment in background.
    """
    job_id = f"j_{uuid.uuid4().hex[:8]}"
    job_record = create_job(job_id=job_id, total=len(payload.products))

    # Schedule background processing
    background_tasks.add_task(
        process_job,
        job_id=job_id,
        products=payload.products,
    )

    return job_record


@router.get("/jobs/{job_id}")
def get_job_endpoint(job_id: str):
    """Retrieve job execution status and live progress counters."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )
    return job


@router.get("/products")
def list_products_endpoint(
    page: int = Query(1, ge=1, description="Page number starting at 1"),
    page_size: int = Query(20, ge=1, le=100, description="Page size up to 100"),
    category: Optional[str] = Query(None, description="Exact category filter"),
    q: Optional[str] = Query(
        None, description="Case-insensitive title search term"
    ),
):
    """List paginated products sorted by SKU with optional category and keyword search."""
    items, total = list_products(
        page=page,
        page_size=page_size,
        category=category,
        q=q,
    )
    formatted = [format_product(it) for it in items]
    return {
        "items": formatted,
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/products/{sku}")
def get_product_endpoint(sku: str):
    """Retrieve a single product by SKU."""
    prod = get_product(sku)
    if not prod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with SKU '{sku}' not found",
        )
    return format_product(prod)


@router.patch("/products/{sku}")
def update_product_endpoint(sku: str, update_req: ProductUpdateRequest):
    """
    Update clean_title, category, or tags of a product and mark status as 'approved'.
    """
    existing = get_product(sku)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with SKU '{sku}' not found",
        )

    updated = update_product_approval(
        sku=sku,
        clean_title=update_req.clean_title,
        category=update_req.category,
        tags=update_req.tags,
    )
    return format_product(updated)
