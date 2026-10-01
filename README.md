# CatalogIQ

CatalogIQ is a high-throughput, asynchronous product catalog enrichment engine. It ingests messy product listings, cleans titles, classifies items into standardized categories, extracts brands, and generates search tags using an LLM pipeline with concurrency control, deduplication, and human-in-the-loop review.

---

## 1. Quickstart (Clean Machine Setup)

### Prerequisites
- Python 3.10+ (tested on Python 3.12)

### Setup Steps
```bash
# 1. Clone repository & navigate to directory
cd CatalogIQ

# 2. Create and activate a virtual environment
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment configuration
# Windows (PowerShell):
Copy-Item .env.example .env
# macOS / Linux:
cp .env.example .env

# 5. Start the server
uvicorn app.main:app --reload --port 8000
```

Open **`http://localhost:8000`** in your browser to access the web dashboard. The SQLite database is automatically initialized at `data/catalogiq.db`.

---

## 2. Running Modes: Mock vs Real LLM

Configuration is controlled via `.env`:

### A. Mock Mode (Default)
Runs locally with zero external API dependencies or costs. Simulates network latency (200ms) and random retryable failures (10%):
```env
LLM_PROVIDER=mock
LLM_CONCURRENCY=5
MOCK_LATENCY_MS=200
MOCK_FAILURE_RATE=0.1
```

### B. Real LLM Mode (Groq / Free Tier)
Connects to Groq Cloud for fast inference using models like `openai/gpt-oss-120b`:
```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
LLM_CONCURRENCY=5
```
*Tip: Get a free API key at [console.groq.com](https://console.groq.com).*

Verify your active provider via health check:
```bash
curl http://localhost:8000/api/health
# {"status":"ok","llm_provider":"groq","llm_concurrency":5}
```

---

## 3. Running the Test Suite

The test suite covers schema validation, database operations, concurrency semaphores, deduplication caching, retry backoffs, and API endpoints:

```bash
# Run all tests (70 tests)
pytest

# Run tests with output and run times
pytest -v

# Run a specific test suite
pytest tests/test_concurrency.py
pytest tests/test_llm_interface.py
```

*Note: Tests run completely isolated using in-memory / temporary databases and mock providers.*

---

## 4. LLM Prompt Design

Enrichment requests use a low-temperature (`0.1`) prompt with structured JSON output enforcement:

### System Prompt
```text
You are an e-commerce catalog enrichment assistant.
Given a raw product title and optional raw description, extract and generate structured catalog attributes.

Output MUST be a valid JSON object with the following fields:
- "clean_title": A clean, readable, standardized product title without promotional fluff or typos.
- "category": Exactly one of: ["Groceries", "Beverages", "Personal Care", "Household", "Electronics", "Fashion", "Home & Kitchen", "Other"]
- "brand": The inferred brand name as a string, or null if unknown or unbranded.
- "tags": A list of up to 5 lowercase keyword tags describing the product.

Respond ONLY with valid JSON.
```

### User Input
```text
Raw Title: {raw_title}
Raw Description: {raw_description}
```

---

## 5. Assumptions & Unfinished Scope

### Key Assumptions Made
1. **Single-Node Deployment:** The current MVP operates on a single server where an in-process `asyncio.Semaphore` and SQLite in WAL mode provide thread-safe, non-blocking reads and writes without external brokers (Redis/Postgres).
2. **Fixed Taxonomy:** Categories are strictly restricted to 8 standard e-commerce verticals.
3. **SKU Authority:** SKU serves as the unique primary key; subsequent batches with matching SKUs update existing catalog records (`ON CONFLICT(sku) DO UPDATE`).
4. **Client-Side CSV Parsing:** Browser parsing via PapaParse offloads CPU overhead and prevents multi-megabyte multipart uploads for typical business batches (100–5,000 items).

### Unfinished / Production Roadmap
- **Distributed Queue (Celery / Redis Streams):** Move beyond in-process `BackgroundTasks` to allow multiple worker nodes to pull from a unified queue.
- **Multi-Product Prompt Batching:** Packing 5–10 items per LLM call to scale throughput and reduce API request count when handling 1M+ items/day.
- **Server Crash Auto-Reconciliation:** An automatic startup scan to re-enqueue items left in `running` status after an unexpected hard server restart.
- **Full-Text Search (FTS5 / Elasticsearch):** Replace substring `LIKE '%query%'` with tokenized FTS indexing to sustain sub-5ms queries on 5M+ product catalogs.
- **Automated Hallucination Scoring:** Cross-checking extracted brands against a canonical brand dictionary to automatically route suspicious products to a `needs_review` queue.
