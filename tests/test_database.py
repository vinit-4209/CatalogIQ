import json
from app.database import init_db, get_connection


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
