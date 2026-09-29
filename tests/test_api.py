import json
import time
import pytest
from fastapi.testclient import TestClient

from app.database import (
    create_job,
    init_db,
    upsert_product,
)
from app.main import app
from app.services.metrics import reset_metrics


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Isolate database for every API test."""
    test_db = tmp_path / "test_api.db"
    monkeypatch.setenv("CATALOGIQ_DB_PATH", str(test_db))
    init_db(test_db)
    reset_metrics()
    return test_db


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_get_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "llm_provider" in data or "provider" in data
    assert "llm_concurrency" in data or "concurrency" in data


def test_get_metrics(client):
    response = client.get("/api/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "llm_calls_total" in data
    assert "llm_errors_total" in data
    assert "max_concurrent_llm_calls" in data


def test_post_jobs_valid(client):
    payload = {
        "products": [
            {
                "sku": "SKU-001",
                "raw_title": "Amul Butter 500g",
                "raw_description": "Pack of 2",
            },
            {
                "sku": "SKU-002",
                "raw_title": "Pepsi Can 300ml",
            },
        ]
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert "id" in data
    assert data["total"] == 2
    assert data["status"] in ("queued", "running")


def test_post_jobs_empty_products(client):
    response = client.post("/api/jobs", json={"products": []})
    assert response.status_code == 400
    assert "error" in response.json()


def test_post_jobs_product_without_sku(client):
    payload = {"products": [{"sku": "", "raw_title": "Valid title"}]}
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 400
    assert "error" in response.json()


def test_post_jobs_product_without_raw_title(client):
    payload = {"products": [{"sku": "SKU-1", "raw_title": "   "}]}
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 400
    assert "error" in response.json()


def test_get_job_existing_and_unknown(client, setup_test_db):
    create_job("j_test123", total=5, db_path=setup_test_db)

    # Existing job
    res_existing = client.get("/api/jobs/j_test123")
    assert res_existing.status_code == 200
    data = res_existing.json()
    assert data["id"] == "j_test123"
    assert data["total"] == 5

    # Unknown job
    res_unknown = client.get("/api/jobs/j_unknown")
    assert res_unknown.status_code == 404
    assert "error" in res_unknown.json()


def test_get_products_pagination_and_sorting(client, setup_test_db):
    for sku in ["SKU-C", "SKU-A", "SKU-B", "SKU-D", "SKU-E"]:
        upsert_product(
            {
                "sku": sku,
                "raw_title": f"Raw {sku}",
                "clean_title": f"Clean {sku}",
                "category": "Groceries",
                "status": "enriched",
            },
            db_path=setup_test_db,
        )

    # Page 1, size 2 -> should get SKU-A, SKU-B
    res1 = client.get("/api/products?page=1&page_size=2")
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["total"] == 5
    assert d1["page"] == 1
    assert d1["page_size"] == 2
    assert len(d1["items"]) == 2
    assert d1["items"][0]["sku"] == "SKU-A"
    assert d1["items"][1]["sku"] == "SKU-B"

    # Page 2, size 2 -> should get SKU-C, SKU-D
    res2 = client.get("/api/products?page=2&page_size=2")
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["items"][0]["sku"] == "SKU-C"
    assert d2["items"][1]["sku"] == "SKU-D"


def test_get_product_by_sku(client, setup_test_db):
    upsert_product(
        {
            "sku": "AMUL-1",
            "raw_title": "Amul butter",
            "clean_title": "Amul Butter 500g",
            "category": "Groceries",
            "brand": "Amul",
            "tags": json.dumps(["butter", "dairy"]),
            "status": "enriched",
        },
        db_path=setup_test_db,
    )

    # Existing SKU
    res = client.get("/api/products/AMUL-1")
    assert res.status_code == 200
    data = res.json()
    assert data["sku"] == "AMUL-1"
    assert data["clean_title"] == "Amul Butter 500g"
    assert data["tags"] == ["butter", "dairy"]

    # Unknown SKU
    res_404 = client.get("/api/products/NONEXISTENT")
    assert res_404.status_code == 404
    assert "error" in res_404.json()


def test_patch_product_sku(client, setup_test_db):
    upsert_product(
        {
            "sku": "PROD-1",
            "raw_title": "messy title",
            "clean_title": "Initial Title",
            "category": "Groceries",
            "brand": "OriginalBrand",
            "tags": json.dumps(["old_tag"]),
            "status": "enriched",
        },
        db_path=setup_test_db,
    )

    patch_payload = {
        "clean_title": "Approved Title",
        "category": "Beverages",
        "tags": ["new_tag_1", "new_tag_2"],
    }
    res = client.patch("/api/products/PROD-1", json=patch_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["sku"] == "PROD-1"
    assert data["clean_title"] == "Approved Title"
    assert data["category"] == "Beverages"
    assert data["tags"] == ["new_tag_1", "new_tag_2"]
    assert data["status"] == "approved"
    assert data["brand"] == "OriginalBrand"

    # Unknown SKU
    res_404 = client.patch(
        "/api/products/NONEXISTENT", json={"clean_title": "Test"}
    )
    assert res_404.status_code == 404


def test_product_filtering_and_search(client, setup_test_db):
    items = [
        {
            "sku": "1",
            "raw_title": "Amul Butter 500g",
            "clean_title": "Amul Butter Salted",
            "category": "Groceries",
        },
        {
            "sku": "2",
            "raw_title": "Peanut butter crunch",
            "clean_title": "Peanut Spread",
            "category": "Groceries",
        },
        {
            "sku": "3",
            "raw_title": "Apple iPhone 15",
            "clean_title": "iPhone 15 Black",
            "category": "Electronics",
        },
        {
            "sku": "4",
            "raw_title": "Diet Pepsi Can",
            "clean_title": "Pepsi Diet 300ml",
            "category": "Beverages",
        },
    ]
    for it in items:
        upsert_product(
            {
                "sku": it["sku"],
                "raw_title": it["raw_title"],
                "clean_title": it["clean_title"],
                "category": it["category"],
                "status": "enriched",
            },
            db_path=setup_test_db,
        )

    # Category exact filter
    res_cat = client.get("/api/products?category=Electronics")
    assert res_cat.status_code == 200
    d_cat = res_cat.json()
    assert d_cat["total"] == 1
    assert d_cat["items"][0]["sku"] == "3"

    # Search q matching raw_title ("peanut butter") and clean_title ("salted butter")
    res_q = client.get("/api/products?q=butter")
    assert res_q.status_code == 200
    d_q = res_q.json()
    assert d_q["total"] == 2
    skus = [x["sku"] for x in d_q["items"]]
    assert "1" in skus and "2" in skus


def test_background_job_processing(client, setup_test_db, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "mock_latency_ms", 0)
    monkeypatch.setattr(settings, "mock_failure_rate", 0.0)

    payload = {
        "products": [
            {"sku": "BG-1", "raw_title": "Amul Butter 500g"},
            {"sku": "BG-2", "raw_title": "Pepsi Can 300ml"},
        ]
    }

    # Returns 202 immediately
    res = client.post("/api/jobs", json=payload)
    assert res.status_code == 202
    job_id = res.json()["id"]

    for _ in range(20):
        res_job = client.get(f"/api/jobs/{job_id}")
        if res_job.json()["status"] == "completed":
            break
        time.sleep(0.05)

    final_job = client.get(f"/api/jobs/{job_id}").json()
    assert final_job["status"] == "completed"
    assert final_job["done"] == 2
