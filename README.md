# NVIDIA Tech Blog Intelligence Agent

A production-ready RAG system that automatically discovers, processes, and answers questions about NVIDIA technical blog content using Google Cloud Platform, Vertex AI, and Gemini.

> **Status**: ✅ Production deployed · Vertex AI RAG Engine · 190+ tests passing

---

## 1. What this project does

This service:

- Watches the **NVIDIA Tech Blog** (via RSS/Atom feed)
- Extracts and normalizes blog content into structured objects
- Summarizes each post with **Gemini 2.0 Flash**
- Ingests summaries into a **RAG backend** (Vertex AI RAG Engine by default)
- Exposes a **Cloud Run HTTP API** so you can:
  - Ask questions about NVIDIA blogs (`POST /ask`)
  - Process multiple questions at once (`POST /ask/batch`)
  - Trigger ingestion of new posts (`POST /ingest`, API-key protected)
  - Check health with dependency status (`GET /health`)
  - View analytics and metrics (`GET /analytics`)
  - Access query history and export data (`GET /history`, `GET /export`)
  - Monitor system health via admin dashboard (`GET /admin/stats`)

It is designed to be:

- **Reliable** – stateful ingestion, duplicate detection, robust RSS parsing, retry logic with exponential backoff
- **Portable** – works against HTTP-based or Vertex AI RAG backends
- **Extensible** – clean protocol-based abstractions for tools and agents
- **Observable** – comprehensive metrics, structured logging, health checks, Cloud Monitoring integration
- **Performant** – response caching, connection pooling, async optimizations, batch processing

---

## 2. High-level architecture

**Core components**

- `contracts/` – Pydantic models (e.g. `BlogPost`, `RawBlogContent`, `BlogSummary`, `RetrievedDoc`)
- `tools/` – Feed discovery, content extraction, summarization, and RAG clients
- `agents/` – Orchestration, summarization agent, QA agent, workflow logic
- `context/` – State management, prefixes, history, compaction
- `eval/` – Evaluation harness for QA quality and regression testing
- `monitoring.py` – Metrics collection, structured logging, health checks
- `caching.py` – Response caching with TTL
- `session_manager.py` – Multi-turn conversation support
- `retry.py` – Retry logic with exponential backoff

**RAG backends**

- **Vertex AI RAG Engine (recommended)**
  - Vertex AI Search + GCS + `text-embedding-005`
  - `GcsRagIngestClient` writes docs → GCS
  - `VertexRagRetrieveClient` queries RAG Engine

- **HTTP-based RAG (optional)**
  - Generic HTTP RAG (e.g. NVIDIA CA-RAG, custom service)
  - `HttpRagIngestClient` and `HttpRagRetrieveClient`

Backend selection is automatic based on environment variables (`USE_VERTEX_RAG`).

**Key technical defaults**

- **Embedding model**: `text-embedding-005`
- **Chunking**: 1024 tokens with 256-token overlap (Vertex AI Search)
- **Hybrid search**: Enabled (vector + keyword/BM25)
- **Reranking**: Available via Vertex AI ranking API
- **Summarization & QA**: Gemini 2.0 Flash
- **Document strategy**: One document per blog post

See `docs/architecture.md` for full details.

---

## 3. Getting started

### 3.1 Prerequisites

- Python **3.10+**
- A **Google Cloud project** with billing enabled
- A **service account** with:
  - Vertex AI + Vertex AI Search permissions
  - Cloud Storage access
- (Recommended) Vertex AI RAG corpus already set up  
  See `docs/deployment.md` for the one-time RAG setup.

### 3.2 Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/nvidia_blog_agent.git
cd nvidia_blog_agent

# Install package (editable mode for development)
pip install -e .

# Optional: with ADK support
pip install -e ".[adk]"

# Configure Google Cloud credentials (for local dev)
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

---

## 4. Configuration

You can use a `.env` file (recommended) or export environment variables directly.

### 4.1 Vertex AI RAG mode (recommended)

```bash
# Gemini config
export GEMINI_MODEL_NAME="gemini-2.0-flash-001"
export GEMINI_LOCATION="us-east5"

# Vertex AI RAG config
export USE_VERTEX_RAG="true"
export RAG_CORPUS_ID="YOUR_CORPUS_ID"      # from Vertex AI RAG Engine
export VERTEX_LOCATION="us-east5"
export RAG_DOCS_BUCKET="gs://nvidia-blog-rag-docs"

# Project + credentials
export GOOGLE_CLOUD_PROJECT="nvidia-blog-agent"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# State (local or GCS)
export STATE_PATH="state.json"
# Recommended for production:
# export STATE_PATH="gs://nvidia-blog-agent-state/state.json"
```

When `USE_VERTEX_RAG=true`, the system automatically uses Vertex AI RAG Engine.

For full setup and deployment, see `docs/deployment.md`.

### 4.2 HTTP-based RAG mode (optional)

```bash
export GEMINI_MODEL_NAME="gemini-2.0-flash-001"
export GEMINI_LOCATION="us-east5"

export RAG_BASE_URL="https://your-rag-service.run.app"
export RAG_UUID="corpus-id"
export RAG_API_KEY="optional-api-key"
```

### 4.3 Optional configuration (v0.2.0 features)

```bash
# API rate limiting
export RATE_LIMIT="10/minute"              # Default: 10/minute
export BATCH_RATE_LIMIT="5/minute"        # Default: 5/minute

# Response caching
export CACHE_MAX_SIZE="1000"               # Default: 1000
export CACHE_TTL_SECONDS="3600"           # Default: 3600 (1 hour)

# Session management
export SESSION_TTL_HOURS="24"              # Default: 24 hours

# Monitoring & logging
export STRUCTURED_LOGGING="false"          # Enable JSON logging
export CORS_ORIGINS="*"                    # CORS allowed origins

# Admin endpoints
export ADMIN_API_KEY="your-admin-key"      # For /admin/* endpoints
export INGEST_API_KEY="your-ingest-key"   # For /ingest endpoint
```

---

## 5. Local usage

### 5.1 Run the test suite

```bash
pytest              # all tests
pytest -v           # verbose
pytest tests/unit/
pytest tests/workflows/
pytest tests/e2e/
```

All tests should pass before changes are merged.

### 5.2 Run ingestion (fetch & index blogs)

```bash
# Default: uses NVIDIA Tech Blog RSS feed and local state.json
python scripts/run_ingest.py

# Use GCS for state persistence
python scripts/run_ingest.py --state-path gs://nvidia-blog-agent-state/state.json

# Custom feed URL (RSS/Atom feed or HTML page)
python scripts/run_ingest.py --feed-url https://custom-blog.com/feed/ --verbose
```

The ingestion pipeline will:

1. Load config and current state
2. Fetch the NVIDIA Tech Blog feed (`https://developer.nvidia.com/blog/feed/` by default)
3. Discover new posts (compares against state)
4. Extract full content from RSS/Atom feed when available (no 403s)
5. Summarize with Gemini 2.0 Flash
6. Ingest documents into the configured RAG backend
7. Update state to avoid reprocessing the same posts

### 5.3 Run QA queries from the CLI

```bash
# Simple question
python scripts/run_qa.py "What did NVIDIA say about RAG on GPUs?"

# Specify number of retrieved docs
python scripts/run_qa.py "Tell me about CUDA" --top-k 10

# Pipe from stdin
echo "What is GPU acceleration?" | python scripts/run_qa.py --top-k 8 --verbose
```

The script will:

1. Create a real RAG client (Vertex or HTTP, depending on config)
2. Retrieve the top K documents (recommended: 8–10, then 4–6 to Gemini)
3. Generate an answer with Gemini 2.0 Flash
4. Print the answer + source titles/URLs

---

## 6. Cloud Run HTTP API

The project includes a FastAPI service for Cloud Run with comprehensive features:

### 6.1 Core Endpoints

- **`GET /health`**: Health check with dependency status
- **`GET /`**: Service information
- **`POST /ask`**: Answer questions using RAG (with caching and session support)
- **`POST /ingest`**: Trigger ingestion (protected by `X-API-Key`)

### 6.2 New Features (v0.2.0)

- **`POST /ask/batch`**: Batch query endpoint for processing multiple questions
- **`GET /analytics`**: Usage analytics and metrics
- **`GET /history`**: Query history (optionally filtered by session_id)
- **`GET /export`**: Export query history in CSV or JSON format
- **`GET /admin/stats`**: Admin dashboard with detailed statistics
- **`POST /admin/cache/clear`**: Clear response cache (admin only)

### 6.3 OpenAPI Documentation

- **`GET /docs`**: Interactive Swagger UI documentation
- **`GET /redoc`**: ReDoc documentation
- **`GET /openapi.json`**: OpenAPI schema

### 6.4 Example Usage

```bash
# Health check with dependency status
curl https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/health

# Ask a question (with session support for multi-turn conversations)
curl -X POST https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is CUDA?", "top_k": 8, "session_id": "my-session-123"}'

# Batch query (process multiple questions at once)
curl -X POST https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/ask/batch \
  -H "Content-Type: application/json" \
  -d '{"questions": ["What is CUDA?", "What is TensorRT?"], "top_k": 8}'

# Get usage analytics
curl https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/analytics

# Get query history for a session
curl "https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/history?session_id=my-session-123"

# Export query history as CSV
curl "https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/export?format=csv&session_id=my-session-123" \
  -o history.csv

# Admin statistics (requires admin API key)
curl -H "X-API-Key: YOUR_ADMIN_API_KEY" \
  https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/admin/stats

# Trigger ingestion (requires API key)
curl -X POST https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_INGEST_API_KEY" \
  -d '{"feed_url": "https://developer.nvidia.com/blog/feed/"}'
```

### 6.5 New Features in v0.2.0

**Monitoring & Observability:**
- Request metrics (counts, latency, error rates, percentiles)
- Structured JSON logging (enable with `STRUCTURED_LOGGING=true`)
- Health checks with dependency status
- Cloud Monitoring integration (optional)

**Performance Optimizations:**
- Response caching for common queries (configurable TTL)
- Connection pooling with HTTP/2 support
- Retry logic with exponential backoff for transient failures
- Async optimizations for batch processing

**API Enhancements:**
- OpenAPI/Swagger documentation at `/docs`
- Rate limiting (configurable via `RATE_LIMIT` env var)
- Batch query endpoint for processing multiple questions
- Usage analytics endpoint

**Additional Features:**
- Multi-turn conversation support via session IDs
- Query history tracking and retrieval
- Export functionality (CSV/JSON formats)
- Admin dashboard endpoints for monitoring and management

You can deploy using the provided script:

```powershell
# PowerShell
$env:RAG_CORPUS_ID = "YOUR_CORPUS_ID"
.\deploy_cloud_run.ps1
```

The script handles:
- Building and pushing the container image
- Setting environment variables and secrets
- Deploying Cloud Run
- Wiring IAM and Artifact Registry

Detailed deployment and Cloud Scheduler setup (daily ingestion) are documented in:
- `docs/deployment.md`
- `docs/development.md`
- `docs/security.md`
- `docs/adding-historical-blogs.md`

---

## 7. Evaluation & quality

An evaluation harness is included to test QA performance:

- Compare RAG configurations (chunking, retrieval parameters, backends)
- Run regression tests on curated questions
- Generate JSON summaries of pass/fail stats

CLI entrypoint:

```bash
python scripts/run_eval_vertex.py --verbose
python scripts/run_eval_vertex.py --output eval_results.json
```

Programmatic usage is documented in `docs/architecture.md`.

---

## 8. MCP integration (optional)

This repo includes an MCP server that wraps the Cloud Run API:

- `nvidia_blog_mcp_server.py` – stdio MCP server

Tools:
- `ask_nvidia_blog` – read-only QA
- `trigger_ingest` – ingestion with API key

See `docs/mcp-setup.md` for configuration and host integration (Cursor, Claude Desktop, etc.).

---

## 9. Project structure (short version)

```
nvidia_blog_agent/
├── nvidia_blog_agent/        # Core Python package
│   ├── contracts/            # Data models
│   ├── tools/                # RSS, scraping, RAG clients
│   ├── agents/               # Summarizer, QA, workflows
│   ├── context/              # State management
│   ├── eval/                 # Evaluation harness
│   ├── monitoring.py         # Metrics & observability
│   ├── caching.py            # Response caching
│   ├── session_manager.py    # Conversation sessions
│   └── retry.py              # Retry logic
├── service/                  # FastAPI Cloud Run service
├── scripts/                  # CLI entrypoints (ingest, QA, eval, tests)
├── tests/                    # 190+ tests
├── docs/                     # Deployment, architecture, security, MCP, etc.
├── Dockerfile
└── pyproject.toml
```

---

## 10. Contributing

Contributions are welcome.

- Please open an issue describing the change you'd like to make
- Ensure all tests pass (`pytest`)
- Follow existing type hints and code style

---

## 11. License

[Add your license information here (e.g. Apache 2.0, MIT).]

---

## 12. Contact

[Add your preferred contact information or GitHub profile here.]

---

**Built with**: Python, FastAPI, Google Cloud Platform, Vertex AI, Gemini 2.0 Flash
