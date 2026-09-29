import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

app = FastAPI(
    title="CatalogIQ",
    description="LLM-powered product catalog enrichment service",
    version="0.1.0",
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_FILE = BASE_DIR / "frontend" / "index.html"


@app.get("/api/health")
def get_health():
    """Health check endpoint returning system status and LLM configuration."""
    provider = os.getenv("LLM_PROVIDER", "mock")
    try:
        concurrency = int(os.getenv("LLM_CONCURRENCY", "5"))
    except ValueError:
        concurrency = 5

    return {
        "status": "ok",
        "llm_provider": provider,
        "llm_concurrency": concurrency,
    }


@app.get("/", response_class=HTMLResponse)
def serve_root():
    """Serve the frontend placeholder."""
    if FRONTEND_FILE.exists():
        return FileResponse(FRONTEND_FILE)
    return HTMLResponse(
        "<!DOCTYPE html><html><body><h1>CatalogIQ</h1><p>Frontend placeholder</p></body></html>"
    )
