from datetime import datetime, timedelta
import json
from app.database import (
    init_db,
    get_connection,
    create_job,
    get_job,
    mark_job_running,
    mark_job_completed,
    IST,
)


def test_database_tables_and_crud(tmp_path):
    test_db_path = tmp_path / "test_catalogiq.db"

    # Initialize tables and indexes in the temporary test database
    init_db(test_db_path)

    conn = get_connection(test_db_path)
    try:
        # Insert one job
        with conn:
            conn.execute(
                """
                INSERT INTO jobs (id, status, total, done, failed, cache_hits, created_at, started_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "j_test1",
                    "completed",
                    10,
                    8,
                    1,
                    1,
                    "2026-09-29T12:00:00",
                    "2026-09-29T12:00:01",
                    "2026-09-29T12:00:05",
                ),
            )

        # Insert one product
        tags_json = json.dumps(["butter", "dairy"])
        with conn:
            conn.execute(
                """
                INSERT INTO products (sku, raw_title, raw_description, clean_title, category, brand, tags, status, error, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "A1",
                    "AMUL butter 500G",
                    "pck of 2",
                    "Amul Butter 500g (Pack of 2)",
                    "Groceries",
                    "Amul",
                    tags_json,
                    "enriched",
                    None,
                    "amul butter 500g pck of 2",
                ),
            )

        # Read back job
        job_row = conn.execute("SELECT * FROM jobs WHERE id = ?", ("j_test1",)).fetchone()
        assert job_row is not None
        assert job_row["id"] == "j_test1"
        assert job_row["status"] == "completed"
        assert job_row["total"] == 10
        assert job_row["done"] == 8
        assert job_row["failed"] == 1
        assert job_row["cache_hits"] == 1
        assert job_row["created_at"] == "2026-09-29T12:00:00"

        # Read back product
        prod_row = conn.execute("SELECT * FROM products WHERE sku = ?", ("A1",)).fetchone()
        assert prod_row is not None
        assert prod_row["sku"] == "A1"
        assert prod_row["raw_title"] == "AMUL butter 500G"
        assert prod_row["raw_description"] == "pck of 2"
        assert prod_row["clean_title"] == "Amul Butter 500g (Pack of 2)"
        assert prod_row["category"] == "Groceries"
        assert prod_row["brand"] == "Amul"
        assert json.loads(prod_row["tags"]) == ["butter", "dairy"]
        assert prod_row["status"] == "enriched"
        assert prod_row["error"] is None
        assert prod_row["content_hash"] == "amul butter 500g pck of 2"
    finally:
        conn.close()


def test_job_timestamps_use_indian_standard_time(tmp_path):
    test_db_path = tmp_path / "test_ist.db"
    init_db(test_db_path)

    # 1. create_job sets created_at with +05:30 offset
    job = create_job("j_ist_1", total=3, db_path=test_db_path)
    assert job["created_at"].endswith("+05:30")
    created_dt = datetime.fromisoformat(job["created_at"])
    assert created_dt.tzinfo is not None
    assert created_dt.utcoffset() == timedelta(hours=5, minutes=30)

    # 2. mark_job_running sets started_at with +05:30 offset
    mark_job_running("j_ist_1", db_path=test_db_path)
    running_job = get_job("j_ist_1", db_path=test_db_path)
    assert running_job["started_at"].endswith("+05:30")
    started_dt = datetime.fromisoformat(running_job["started_at"])
    assert started_dt.utcoffset() == timedelta(hours=5, minutes=30)

    # 3. mark_job_completed sets finished_at with +05:30 offset
    mark_job_completed("j_ist_1", db_path=test_db_path)
    completed_job = get_job("j_ist_1", db_path=test_db_path)
    assert completed_job["finished_at"].endswith("+05:30")
    finished_dt = datetime.fromisoformat(completed_job["finished_at"])
    assert finished_dt.utcoffset() == timedelta(hours=5, minutes=30)

