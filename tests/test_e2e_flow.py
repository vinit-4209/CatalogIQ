import csv
import time
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import init_db, upsert_product
from app.main import app
from app.services.metrics import reset_metrics


@pytest.fixture
def e2e_client(tmp_path, monkeypatch):
    test_db = tmp_path / "test_e2e.db"
    monkeypatch.setenv("CATALOGIQ_DB_PATH", str(test_db))
    monkeypatch.setattr(settings, "llm_provider", "mock")
    monkeypatch.setattr(settings, "mock_latency_ms", 0)
    monkeypatch.setattr(settings, "mock_failure_rate", 0.0)
    init_db(test_db)
    reset_metrics()
    with TestClient(app) as client:
        yield client, test_db


def test_end_to_end_frontend_flow(e2e_client):
    client, test_db = e2e_client

    # 1. Open /
    r_root = client.get("/")
    assert r_root.status_code == 200
    assert "CatalogIQ" in r_root.text
    assert 'id="csvFileInput"' in r_root.text
    assert 'id="jobStatusCard"' in r_root.text
    assert 'id="productsTable"' in r_root.text
    assert 'id="editModal"' in r_root.text

    # 2. Static files
    r_css = client.get("/style.css")
    r_js = client.get("/app.js")
    assert r_css.status_code == 200
    assert r_js.status_code == 200

    # 3. Seed a failed product
    upsert_product({
        "sku": "FAIL-999",
        "raw_title": "Unparseable Corrupt Product Data",
        "raw_description": "Random gibberish",
        "clean_title": None,
        "category": None,
        "brand": None,
        "tags": None,
        "status": "failed",
        "error": "LLM validation failed: output exceeded max attempts",
        "content_hash": "fail999hash",
    }, db_path=test_db)

    # 4. Upload CSV simulation
    with open("data/test_products.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        products = [
            {
                "sku": r["sku"],
                "raw_title": r["raw_title"],
                "raw_description": r.get("raw_description"),
            }
            for r in reader
        ]

    assert len(products) == 3

    # 5. POST /api/jobs
    r_job = client.post("/api/jobs", json={"products": products})
    assert r_job.status_code == 202
    job_data = r_job.json()
    job_id = job_data["id"]
    assert job_data["total"] == 3

    # 6. Poll GET /api/jobs/{job_id}
    st = job_data["status"]
    for _ in range(30):
        r_poll = client.get(f"/api/jobs/{job_id}")
        assert r_poll.status_code == 200
        st = r_poll.json()["status"]
        if st in ("completed", "failed"):
            break
        time.sleep(0.05)

    assert st == "completed"

    # 7. Catalogue listing & failed product check
    r_prods = client.get("/api/products")
    assert r_prods.status_code == 200
    items = r_prods.json()["items"]
    fail_item = next((p for p in items if p["sku"] == "FAIL-999"), None)
    assert fail_item is not None
    assert fail_item["status"] == "failed"
    assert "LLM validation failed" in fail_item["error"]

    # 8. Category filter
    r_cat = client.get("/api/products?category=Electronics")
    assert r_cat.status_code == 200
    for it in r_cat.json()["items"]:
        assert it["category"] == "Electronics"

    # 9. Debounced Search
    r_search = client.get("/api/products?q=Ghee")
    assert r_search.status_code == 200
    assert len(r_search.json()["items"]) >= 1

    # 10. Product review / edit (PATCH)
    r_patch = client.patch(
        "/api/products/FAIL-999",
        json={
            "clean_title": "Manual Approved Product 999",
            "category": "Groceries",
            "tags": ["manual", "approved"],
        },
    )
    assert r_patch.status_code == 200
    patched = r_patch.json()
    assert patched["status"] == "approved"
    assert patched["clean_title"] == "Manual Approved Product 999"
    assert patched["tags"] == ["manual", "approved"]
