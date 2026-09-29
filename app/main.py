from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to initialize resources on startup."""
    init_db()
    yield


app = FastAPI(
    title="CatalogIQ",
    description="LLM-powered product catalog enrichment service",
    version="0.1.0",
    lifespan=lifespan,
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_FILE = BASE_DIR / "frontend" / "index.html"


@app.get("/api/health")
def get_health():
    """Health check endpoint returning system status and LLM configuration."""
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "llm_concurrency": settings.llm_concurrency,
    }


@app.get("/", response_class=HTMLResponse)
def serve_root():
    """Serve the frontend placeholder."""
    if FRONTEND_FILE.exists():
        return FileResponse(FRONTEND_FILE)
    return HTMLResponse(
        "<!DOCTYPE html><html><body><h1>CatalogIQ</h1><p>Frontend placeholder</p></body></html>"
    )
