# NVIDIA Blog Agent - Deep Project Inventory

**Generated**: 2025-01-XX  
**Status**: ✅ Production Deployed  
**Service URL**: `https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app`

---

## 1. Project Overview

### Purpose
A production-ready RAG (Retrieval-Augmented Generation) system that automatically:
- Discovers NVIDIA Tech Blog posts via RSS/Atom feeds
- Extracts and normalizes blog content
- Summarizes posts using Gemini 2.0 Flash
- Ingests summaries into Vertex AI RAG Engine
- Provides a Cloud Run HTTP API for querying blog content
- Exposes MCP (Model Context Protocol) tools for AI assistants

### Current Status
- ✅ **Production Deployed**: Cloud Run service operational
- ✅ **Automated Ingestion**: Cloud Scheduler running daily at 7:00 AM ET
- ✅ **Test Coverage**: 208 tests collected
- ✅ **RAG Backend**: Vertex AI RAG Engine with 100+ documents indexed
- ✅ **MCP Integration**: Both stdio and HTTP/SSE endpoints available

---

## 2. Architecture & Components

### Core Package Structure (`nvidia_blog_agent/`)

#### Contracts (`contracts/`)
- **Purpose**: Pydantic data models
- **Key Models**:
  - `BlogPost`: Raw blog post structure
  - `RawBlogContent`: Extracted HTML content
  - `BlogSummary`: Summarized blog post
  - `RetrievedDoc`: RAG retrieval results

#### Tools (`tools/`)
- **discovery.py**: RSS/Atom feed parsing, blog post discovery
- **scraper.py**: HTML content extraction and cleaning
- **http_fetcher.py**: HTTP client for fetching feeds and pages
- **summarization.py**: Summarization protocol/interface
- **rag_ingest.py**: RAG ingestion protocol
- **rag_retrieve.py**: RAG retrieval protocol
- **gcs_rag_ingest.py**: Vertex AI RAG ingestion (GCS-based)
- **vertex_rag_retrieve.py**: Vertex AI RAG retrieval client

#### Agents (`agents/`)
- **workflow.py**: Main ingestion pipeline orchestration
- **summarizer_agent.py**: Summarization agent protocol
- **gemini_summarizer.py**: Gemini-based summarization implementation
- **qa_agent.py**: Question-answering agent
- **gemini_qa_model.py**: Gemini QA model implementation

#### Context (`context/`)
- **state_persistence.py**: State loading/saving (local JSON or GCS)
- **session_config.py**: Session state management
- **compaction.py**: State history compaction

#### Evaluation (`eval/`)
- **harness.py**: QA evaluation harness for regression testing

#### Core Modules
- **config.py**: Environment-based configuration loading
- **rag_clients.py**: RAG client factory (Vertex vs HTTP)
- **monitoring.py**: Metrics collection, structured logging, health checks
- **caching.py**: Response caching with TTL
- **session_manager.py**: Multi-turn conversation support
- **retry.py**: Retry logic with exponential backoff
- **secrets.py**: Google Cloud Secret Manager integration

### Service Layer (`service/`)

#### FastAPI Application (`app.py`)
**Endpoints**:
- `GET /`: Service information
- `GET /health`: Health check with dependency status
- `POST /ask`: Answer questions using RAG (with caching and session support)
- `POST /ask/batch`: Batch query endpoint (process multiple questions)
- `POST /ingest`: Trigger ingestion pipeline (protected by API key)
- `GET /analytics`: Usage analytics and metrics
- `GET /history`: Query history (optionally filtered by session_id)
- `GET /export`: Export query history (CSV/JSON)
- `GET /admin/stats`: Admin dashboard with detailed statistics
- `POST /admin/cache/clear`: Clear response cache (admin only)
- `GET /docs`: Swagger UI documentation
- `GET /redoc`: ReDoc documentation
- `GET /openapi.json`: OpenAPI schema

**Features**:
- Rate limiting (configurable via `RATE_LIMIT`, `BATCH_RATE_LIMIT`)
- Response caching (configurable TTL)
- Multi-turn conversation support (session management)
- Structured logging (JSON format optional)
- Metrics collection (request counts, latency, error rates)
- CORS middleware
- Health checks with dependency status

#### MCP HTTP Endpoint (`mcp_http.py`)
- FastMCP-based HTTP/SSE transport
- Mounted at `/mcp` endpoint
- Stateless mode for Cloud Run
- Direct integration with service components (no HTTP overhead)

### MCP Server (`mcp/`)

#### Stdio Server (`nvidia_blog_mcp_server.py`)
- Runs as stdio subprocess for MCP hosts
- Connects directly to Vertex AI RAG and Gemini (bypasses Cloud Run)
- Tool: `ask_nvidia_blog` (read-only QA tool)

#### Wrapper Script (`run_mcp_server.py`)
- Path resolution for stdio server
- Auto-detects project structure

### Scripts (`scripts/`)

#### CLI Entry Points
- **run_ingest.py**: Run ingestion pipeline (discover → scrape → summarize → ingest)
- **run_qa.py**: Query QA agent from command line
- **run_eval_vertex.py**: Run evaluation harness against Vertex RAG
- **import_rag_files.py**: Import historical blog files to GCS
- **test_service_local.py**: Local service testing script
- **test_rss_feed.py**: RSS feed parsing test script
- **kaggle_notebook_example.py**: Example notebook code

---

## 3. Dependencies

### Core Dependencies (`requirements.txt`, `pyproject.toml`)

#### Python Version
- **Requires**: Python 3.10+

#### Core Libraries
- **pydantic** (>=2.0.0,<3.0.0): Data validation and models
- **httpx[http2]** (>=0.25.0): HTTP client with HTTP/2 support
- **beautifulsoup4** (>=4.12.0): HTML parsing
- **lxml** (>=4.9.0): XML/HTML parser
- **python-dateutil** (>=2.8.0): Date/time handling

#### Google Cloud
- **google-generativeai** (>=0.3.0): Gemini API client
- **google-cloud-storage** (>=2.10.0): GCS client
- **google-cloud-aiplatform** (>=1.38.0): Vertex AI client
- **google-cloud-secret-manager** (>=2.16.0): Secret Manager client
- **google-cloud-monitoring** (>=2.15.0): Cloud Monitoring integration

#### Web Framework
- **fastapi** (>=0.104.0): FastAPI web framework
- **uvicorn[standard]** (>=0.24.0): ASGI server
- **slowapi** (>=0.1.9): Rate limiting
- **python-multipart** (>=0.0.6): Form data handling

#### MCP (Model Context Protocol)
- **mcp** (>=1.0.0): MCP SDK for Python

#### Utilities
- **python-dotenv** (>=1.0.0): Environment variable loading
- **cachetools** (>=5.3.0): Caching utilities
- **prometheus-client** (>=0.19.0): Prometheus metrics (optional)

#### Optional Dependencies
- **google-genai-adk** (>=0.1.0): Google ADK support (optional)
- **pytest** (>=7.4.0): Testing framework
- **pytest-asyncio** (>=0.21.0): Async test support

---

## 4. Configuration

### Environment Variables

#### Required (Vertex AI RAG Mode)
- `USE_VERTEX_RAG`: Set to `"true"` to enable Vertex AI RAG Engine
- `RAG_CORPUS_ID`: Vertex AI RAG corpus ID (numeric)
- `VERTEX_LOCATION`: Region for Vertex AI (e.g., `us-east5`)
- `RAG_DOCS_BUCKET`: GCS bucket for documents (e.g., `gs://nvidia-blog-rag-docs`)
- `GEMINI_MODEL_NAME`: Gemini model name (e.g., `gemini-2.0-flash-001`)
- `GEMINI_LOCATION`: Region for Gemini API (e.g., `us-east5`)
- `GOOGLE_CLOUD_PROJECT`: GCP project ID

#### Optional
- `STATE_PATH`: State persistence path (default: `state.json`, production: `gs://bucket/state.json`)
- `RATE_LIMIT`: Rate limit for `/ask` endpoint (default: `10/minute`)
- `BATCH_RATE_LIMIT`: Rate limit for `/ask/batch` (default: `5/minute`)
- `CACHE_MAX_SIZE`: Response cache size (default: `1000`)
- `CACHE_TTL_SECONDS`: Cache TTL (default: `3600`)
- `SESSION_TTL_HOURS`: Session TTL (default: `24`)
- `STRUCTURED_LOGGING`: Enable JSON logging (default: `false`)
- `CORS_ORIGINS`: CORS allowed origins (default: `*`)

#### Secrets (Secret Manager)
- `INGEST_API_KEY`: API key for `/ingest` endpoint (Secret Manager: `ingest-api-key`)
- `ADMIN_API_KEY`: Optional API key for `/admin/*` endpoints (Secret Manager: `admin-api-key`)
- `RAG_API_KEY`: Optional RAG service API key (Secret Manager: `rag-api-key`)

#### Local Development
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account JSON (local dev only)

### Configuration Loading
- Configuration loaded via `nvidia_blog_agent.config.load_config_from_env()`
- Supports `.env` file (via `python-dotenv`)
- Automatic fallback to environment variables
- Secrets loaded from Secret Manager with environment variable fallback

---

## 5. RAG Backend Architecture

### Vertex AI RAG Engine (Primary/Recommended)

#### Components
- **Vertex AI RAG Engine**: Manages retrieval and grounding
- **Vertex AI Search**: Provides corpus and indexing backend
- **Google Cloud Storage**: Document storage (`gs://nvidia-blog-rag-docs`)

#### Embedding Model
- **Model**: `text-embedding-005` (default, high quality)
- **Dimension**: Full/default embedding dimension
- **Usage**: Automatically used by Vertex AI RAG Engine

#### Retrieval Configuration
- **Hybrid Search**: Enabled (vector + keyword/BM25)
- **Reranking**: Available via Vertex AI ranking API
- **Chunking**: 1024 tokens with 256-token overlap
- **Initial Retrieval**: `top_k=8-10` documents (recommended)
- **QA Input**: Top 4-6 documents passed to Gemini (after reranking)

#### Document Strategy
- **One document per blog post**: Each blog post becomes one RAG document
- **Content**: Full cleaned text from `RawBlogContent.text`
- **Storage**: Documents written to GCS as `{blog_id}.txt` files
- **Metadata**: Stored as `{blog_id}.metadata.json` files in GCS

### HTTP-based RAG (Legacy/Alternative)
- Triggered when `USE_VERTEX_RAG` is not set or `false`
- Uses `HttpRagIngestClient` and `HttpRagRetrieveClient`
- Requires: `RAG_BASE_URL`, `RAG_UUID`

---

## 6. Data Flow & Pipeline

### Ingestion Pipeline
1. **Discovery**: Parse NVIDIA blog RSS/Atom feed or HTML
   - Supports RSS 2.0 and Atom feed formats
   - Extracts full HTML content from feed entries when available
   - Falls back to HTML page parsing if feed format not detected
2. **Scraping**: Use feed content directly or fetch individual pages
   - Smart content usage: Uses RSS feed content when available
   - Fallback fetching: Only fetches pages when feed content unavailable
3. **Summarization**: Generate summaries using Gemini 2.0 Flash
4. **Ingestion**: Write documents to RAG backend (GCS for Vertex RAG)
5. **State Update**: Update persisted state with new post IDs

### QA Pipeline
1. **Retrieval**: Retrieve relevant documents from RAG backend (`top_k=8-10`)
2. **Reranking**: Optional semantic reranking (Vertex AI)
3. **Answer Generation**: Generate answer using Gemini 2.0 Flash (top 4-6 docs)
4. **Response**: Return answer with source citations

### State Management
- **System State**: Uses `app:` prefix
  - `app:last_seen_blog_ids`: Set of previously seen blog post IDs
  - `app:last_ingestion_results`: Results from most recent ingestion
  - `app:ingestion_history`: Historical record of ingestion runs
- **User State**: Reserved for future ADK/Vertex Agent integration (`user:` prefix)
- **Persistence**: Supports local JSON files or GCS URIs

---

## 7. Testing

### Test Structure
- **Total Tests**: 208 tests collected
- **Test Categories**:
  - `tests/unit/`: Unit tests for individual components
  - `tests/integration/`: Integration tests
  - `tests/e2e/`: End-to-end tests
  - `tests/workflows/`: Workflow tests
  - `tests/agents/`: Agent tests
  - `tests/context/`: Context/state management tests

### Test Files
- `tests/unit/test_contracts.py`: Data model tests
- `tests/unit/tools/`: Tool tests (discovery, scraper, RAG, summarization)
- `tests/agents/test_qa_agent.py`: QA agent tests
- `tests/agents/test_summarizer_agent.py`: Summarizer agent tests
- `tests/e2e/test_full_run_smoke.py`: Full pipeline smoke tests
- `tests/e2e/test_eval_harness_regression.py`: Evaluation harness regression tests
- `tests/workflows/test_daily_pipeline_sequential.py`: Sequential pipeline tests
- `tests/workflows/test_parallel_scraping.py`: Parallel scraping tests
- `tests/context/test_compaction_behavior.py`: State compaction tests
- `tests/context/test_session_state_prefixes.py`: Session state prefix tests
- `tests/integration/test_wif_validation.py`: Workload Identity Federation tests

### Running Tests
```bash
pytest              # All tests
pytest -v           # Verbose
pytest tests/unit/  # Unit tests only
pytest tests/e2e/   # E2E tests only
```

---

## 8. Deployment

### Cloud Run Service
- **Service URL**: `https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app`
- **Status**: ✅ Operational
- **Region**: `us-central1`
- **Container**: Multi-stage Docker build (Python 3.11-slim)
- **Health Check**: `/health` endpoint with dependency status

### Cloud Scheduler
- **Job Name**: `nvidia-blog-daily-ingest`
- **Schedule**: Daily at 7:00 AM ET (`0 7 * * *` in America/New_York timezone)
- **Status**: ✅ Operational
- **Authentication**: OIDC (OpenID Connect)
- **Endpoint**: `POST /ingest` (protected by API key)

### CI/CD
- **Primary Method**: GitHub Actions (automated deployment)
- **Trigger**: Push to `master` branch or manual trigger
- **Process**: Tests → Build → Push to Artifact Registry → Deploy to Cloud Run → Health Check
- **Documentation**: `docs/ci-cd.md`

### Manual Deployment
- **Scripts**: PowerShell scripts for manual deployment (legacy)
- **Note**: For production, use automated CI/CD pipeline

---

## 9. Documentation

### Documentation Files (`docs/`)
- **architecture.md**: System architecture and technical details
- **deployment.md**: Complete deployment guide (Vertex AI RAG, Cloud Run, Scheduler)
- **development.md**: Local development setup
- **security.md**: Security practices and secrets management
- **ci-cd.md**: CI/CD pipeline documentation
- **workload-identity-federation.md**: WIF setup guide
- **adding-historical-blogs.md**: Guide for adding historical blog content
- **mcp/mcp-setup.md**: MCP server configuration and troubleshooting

### README
- **README.md**: Comprehensive user-facing documentation
  - Project overview
  - Getting started guide
  - Configuration examples
  - API usage examples
  - Evaluation guide
  - MCP integration guide

---

## 10. Git Status & Recent Changes

### Modified Files
- `README.md`: Updated documentation
- `docs/deployment.md`: Updated deployment documentation
- `docs/security.md`: Updated security documentation
- `pyproject.toml`: Updated dependencies
- `requirements.txt`: Updated dependencies
- `scripts/test_service_local.py`: Updated test script

### Deleted Files
- `deploy_cloud_run.ps1`: Removed (replaced by CI/CD)
- `docs/cloud-resources-inventory.md`: Removed
- `docs/directory-inventory.md`: Removed
- `docs/mcp-authentication-fix.md`: Removed
- `docs/mcp-setup.md`: Removed (moved to `mcp/mcp-setup.md`)
- `mcp.json`: Removed (should be in `.cursor/mcp.json`)
- `nvidia_blog_mcp_server.py`: Removed (moved to `mcp/nvidia_blog_mcp_server.py`)
- `run_mcp_server.py`: Removed (moved to `mcp/run_mcp_server.py`)
- `setup_scheduler.ps1`: Removed
- `smoke_test_payload.json`: Removed
- `test_mcp_config.py`: Removed
- `test_mcp_entrypoint.py`: Removed

### Untracked Files
- `mcp/`: New MCP server directory
- `nvidia_blog_agent/secrets.py`: New Secret Manager integration

### Observations
- **MCP Server Reorganization**: MCP server files moved to dedicated `mcp/` directory
- **CI/CD Migration**: PowerShell deployment scripts removed in favor of GitHub Actions
- **Documentation Cleanup**: Removed redundant documentation files
- **Secret Management**: New `secrets.py` module for Secret Manager integration

---

## 11. Code Statistics

### Function/Class Count
- **Total Functions/Classes**: 183 matches across 51 files
- **Main Entry Points**: 6 scripts (`run_ingest.py`, `run_qa.py`, `run_eval_vertex.py`, etc.)
- **Service Endpoints**: 11 HTTP endpoints in `service/app.py`
- **MCP Tools**: 1 tool (`ask_nvidia_blog`)

### File Structure
- **Python Package**: `nvidia_blog_agent/` (core package)
- **Service Layer**: `service/` (FastAPI application)
- **MCP Server**: `mcp/` (MCP stdio server)
- **Scripts**: `scripts/` (CLI entry points)
- **Tests**: `tests/` (test suite)
- **Documentation**: `docs/` (documentation files)

---

## 12. Security

### Secrets Management
- ✅ **Secret Manager Integration**: `nvidia_blog_agent/secrets.py`
- ✅ **Environment Variable Fallback**: Automatic fallback for local development
- ✅ **No Hardcoded Secrets**: All secrets loaded from environment or Secret Manager
- ✅ **`.gitignore`**: Properly excludes `.env`, `*-sa.json`, `state.json`

### API Security
- **API Key Protection**: `/ingest` and `/admin/*` endpoints protected by API keys
- **CORS**: Configurable CORS origins
- **Rate Limiting**: Configurable rate limits per endpoint
- **Health Checks**: Dependency status monitoring

### Audit Status
- **Last Audit**: 2025-11-25
- **Status**: ✅ SECURE - No secrets exposed
- **Details**: See `docs/security.md`

---

## 13. Monitoring & Observability

### Metrics
- **Request Metrics**: Counts, latency, error rates, percentiles
- **Cache Stats**: Hit rate, size, TTL
- **Session Stats**: Active sessions, queries per session
- **Health Checks**: Dependency status (RAG backend, QA agent)

### Logging
- **Structured Logging**: Optional JSON format (via `STRUCTURED_LOGGING` env var)
- **Cloud Logging**: Integrated with Google Cloud Logging
- **Log Levels**: Configurable via standard Python logging

### Health Checks
- **Endpoint**: `GET /health`
- **Dependencies Checked**: RAG backend, QA agent
- **Status Codes**: 200 (healthy), 503 (unhealthy)

---

## 14. MCP Integration

### Available Tools
- **`ask_nvidia_blog`**: Ask questions about NVIDIA Tech Blogs
  - Parameters: `question` (required), `top_k` (optional, default: 8, range: 1-20)
  - Returns: Answer with source citations
  - Read-only (no ingestion tool - handled by Cloud Scheduler)

### MCP Server Modes
1. **HTTP/SSE Endpoint** (Recommended): Direct connection to Cloud Run at `/mcp`
   - No local setup required
   - Uses FastMCP with streamable HTTP transport
   - Stateless mode for Cloud Run scalability
2. **Local Stdio Server**: Runs locally, connects to Vertex AI RAG directly
   - Requires local Python environment
   - Uses `mcp/nvidia_blog_mcp_server.py`
   - Faster (bypasses Cloud Run HTTP overhead)

### Configuration
- **Cursor IDE**: Copy `mcp.json` to `.cursor/mcp.json`
- **Documentation**: `mcp/mcp-setup.md`

---

## 15. Key Features

### v0.2.0 Features
- **Batch Query Endpoint**: Process multiple questions at once
- **Usage Analytics**: Request metrics, cache stats, session stats
- **Query History**: Track and retrieve query history
- **Export Functionality**: Export history in CSV/JSON format
- **Admin Dashboard**: Detailed statistics and cache management
- **Multi-turn Conversations**: Session support for context-aware queries
- **Response Caching**: Configurable TTL-based caching
- **Rate Limiting**: Configurable per-endpoint rate limits
- **OpenAPI Documentation**: Swagger UI and ReDoc

### Production Features
- **Automated Ingestion**: Daily Cloud Scheduler job
- **State Persistence**: GCS-based state management
- **Health Monitoring**: Dependency health checks
- **Structured Logging**: JSON logging support
- **Metrics Collection**: Request metrics and analytics
- **Secret Management**: Google Cloud Secret Manager integration

---

## 16. Project Health

### ✅ Strengths
- **Comprehensive Test Coverage**: 208 tests
- **Production Deployed**: Fully operational Cloud Run service
- **Automated CI/CD**: GitHub Actions pipeline
- **Well Documented**: Extensive documentation
- **Security Best Practices**: Secret Manager integration, no hardcoded secrets
- **Monitoring**: Comprehensive metrics and health checks
- **MCP Integration**: Both stdio and HTTP/SSE endpoints

### 🔄 Recent Improvements
- MCP server reorganization (moved to `mcp/` directory)
- CI/CD migration (removed PowerShell scripts)
- Secret Manager integration (`secrets.py`)
- Documentation cleanup (removed redundant files)

### 📋 Recommendations
1. **Version Update**: Update `pyproject.toml` version from `0.1.0` to `0.2.0` (README indicates v0.2.0 features)
2. **Test Execution**: Run full test suite to verify all 208 tests pass
3. **Documentation Sync**: Ensure all documentation reflects current state
4. **Git Cleanup**: Consider committing or removing untracked files (`mcp/`, `secrets.py`)

---

## 17. Quick Reference

### Service URLs
- **Cloud Run**: `https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app`
- **Health Check**: `https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/health`
- **API Docs**: `https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/docs`
- **MCP Endpoint**: `https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/mcp`

### Key Commands
```bash
# Run ingestion
python scripts/run_ingest.py

# Run QA query
python scripts/run_qa.py "What is CUDA?"

# Run tests
pytest

# Run evaluation
python scripts/run_eval_vertex.py
```

### Configuration Files
- **Project Config**: `pyproject.toml`
- **Dependencies**: `requirements.txt`
- **Docker**: `Dockerfile`
- **MCP Config**: `.cursor/mcp.json` (not in repo)

---

**End of Inventory**

