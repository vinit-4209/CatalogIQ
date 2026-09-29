from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.database import init_db
from app.routes import api_router


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

# Exception handlers ensuring uniform {"error": "message"} responses and HTTP 400 for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    first_error = exc.errors()[0]
    error_msg = first_error.get("msg", "Validation error")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": error_msg},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


# Include API endpoints under /api
app.include_router(api_router)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_FILE = BASE_DIR / "frontend" / "index.html"


@app.get("/", response_class=HTMLResponse)
def serve_root():
    """Serve the frontend placeholder."""
    if FRONTEND_FILE.exists():
        return FileResponse(FRONTEND_FILE)
    return HTMLResponse(
        "<!DOCTYPE html><html><body><h1>CatalogIQ</h1><p>Frontend placeholder</p></body></html>"
    )
