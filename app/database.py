import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "catalogiq.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    total INTEGER NOT NULL DEFAULT 0,
    done INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    cache_hits INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS products (
    sku TEXT PRIMARY KEY,
    raw_title TEXT NOT NULL,
    raw_description TEXT,
    clean_title TEXT,
    category TEXT,
    brand TEXT,
    tags TEXT,
    status TEXT NOT NULL,
    error TEXT,
    content_hash TEXT
);

CREATE INDEX IF NOT EXISTS idx_products_content_hash ON products(content_hash);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
"""


def get_connection(db_path: Union[Path, str] = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Create and return a configured SQLite connection."""
    if str(db_path) != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn


def init_db(db_target: Union[Path, str, sqlite3.Connection] = DEFAULT_DB_PATH) -> None:
    """Initialize database tables and indexes."""
    if isinstance(db_target, sqlite3.Connection):
        db_target.executescript(SCHEMA_SQL)
        return

    conn = get_connection(db_target)
    try:
        with conn:
            conn.executescript(SCHEMA_SQL)
    finally:
        conn.close()


def create_job(
    job_id: str, total: int, db_path: Union[Path, str] = DEFAULT_DB_PATH
) -> dict:
    """Insert a new job with 'queued' status."""
    created_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO jobs (id, status, total, done, failed, cache_hits, created_at)
                VALUES (?, 'queued', ?, 0, 0, 0, ?)
                """,
                (job_id, total, created_at),
            )
        return {
            "id": job_id,
            "status": "queued",
            "total": total,
            "done": 0,
            "failed": 0,
            "cache_hits": 0,
            "created_at": created_at,
            "started_at": None,
            "finished_at": None,
        }
    finally:
        conn.close()


def get_job(
    job_id: str, db_path: Union[Path, str] = DEFAULT_DB_PATH
) -> Optional[dict]:
    """Retrieve a job by ID."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def mark_job_running(
    job_id: str, db_path: Union[Path, str] = DEFAULT_DB_PATH
) -> None:
    """Update job status to 'running' and set started_at timestamp."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                "UPDATE jobs SET status = 'running', started_at = ? WHERE id = ?",
                (now, job_id),
            )
    finally:
        conn.close()


def mark_job_completed(
    job_id: str, db_path: Union[Path, str] = DEFAULT_DB_PATH
) -> None:
    """Update job status to 'completed' and set finished_at timestamp."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                "UPDATE jobs SET status = 'completed', finished_at = ? WHERE id = ?",
                (now, job_id),
            )
    finally:
        conn.close()


def increment_job_counter(
    job_id: str, counter: str, db_path: Union[Path, str] = DEFAULT_DB_PATH
) -> None:
    """Atomically increment done, failed, or cache_hits counter for a job."""
    if counter not in ("done", "failed", "cache_hits"):
        raise ValueError(f"Invalid counter: {counter}")
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                f"UPDATE jobs SET {counter} = {counter} + 1 WHERE id = ?",
                (job_id,),
            )
    finally:
        conn.close()


def upsert_product(
    data: dict, db_path: Union[Path, str] = DEFAULT_DB_PATH
) -> None:
    """Insert or update a product record."""
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO products (
                    sku, raw_title, raw_description, clean_title, category, brand, tags, status, error, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sku) DO UPDATE SET
                    raw_title = excluded.raw_title,
                    raw_description = excluded.raw_description,
                    clean_title = excluded.clean_title,
                    category = excluded.category,
                    brand = excluded.brand,
                    tags = excluded.tags,
                    status = excluded.status,
                    error = excluded.error,
                    content_hash = excluded.content_hash
                """,
                (
                    data["sku"],
                    data["raw_title"],
                    data.get("raw_description"),
                    data.get("clean_title"),
                    data.get("category"),
                    data.get("brand"),
                    data.get("tags"),
                    data["status"],
                    data.get("error"),
                    data.get("content_hash"),
                ),
            )
    finally:
        conn.close()


def get_product(
    sku: str, db_path: Union[Path, str] = DEFAULT_DB_PATH
) -> Optional[dict]:
    """Retrieve a product by SKU."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
