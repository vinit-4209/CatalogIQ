# CatalogIQ

CatalogIQ is a service designed to take messy product listings from marketplaces and quick-commerce platforms and use an LLM pipeline to turn them into a clean, searchable catalogue.

## Architecture Principles
- **Minimal & Lightweight**: Built for a 2-day internship assignment scope using Python, FastAPI, SQLite, and vanilla HTML/CSS/JS.
- **No Over-Engineering**: No Redis, Celery, Docker, React, or microservices.
- **Controlled Concurrency**: Bounded parallel calls to protect LLM rate limits.
- **Resilience**: Retries with exponential backoff and deduplication/caching.

---

## Project Structure

```
CatalogIQ/
├── app/
│   ├── __init__.py
│   └── main.py          # FastAPI application & endpoints
├── frontend/
│   └── index.html       # Vanilla HTML/CSS/JS UI placeholder
├── tests/               # Unit and integration tests (upcoming)
├── data/                # Sample datasets / CSVs (upcoming)
├── .env.example         # Template for environment variables
├── .gitignore           # Git ignore rules
├── requirements.txt     # Python dependencies
├── DESIGN.md            # System design & architecture document
└── README.md            # Project documentation & runbook
```

---

## Getting Started

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.12)

### 2. Setup Virtual Environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

### 5. Run Server
```bash
uvicorn app.main:app --reload --port 8000
```
The server will start at `http://localhost:8000`.

---

## Health Check Verification
```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{
  "status": "ok",
  "llm_provider": "mock",
  "llm_concurrency": 5
}
```

---

## Implementation Status
- [x] Initial project skeleton and FastAPI server setup
- [ ] Database schema & persistence (SQLite)
- [ ] LLM provider interface (Mock & Real)
- [ ] Background job processing & concurrency control
- [ ] In-flight deduplication & caching
- [ ] Product catalogue & search APIs
- [ ] Frontend single-page app (vanilla JS)
- [ ] Unit & concurrency test suite
