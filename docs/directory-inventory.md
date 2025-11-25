# Directory Inventory

**Project:** nvidia_blog_agent  
**Location:** `Z:\SynapGarden\nvidia_blog_agent`  
**Last Updated:** 2025-11-24  
**Total Files (excluding cache):** 84  
**Total Size:** 537.99 KB (0.53 MB)

---

## Root Level Files

### Configuration Files
- `pyproject.toml` (1,073 bytes) - Python project configuration and dependencies
- `requirements.txt` (746 bytes) - Python package dependencies
- `Dockerfile` (2,071 bytes) - Docker container configuration
- `.dockerignore` (528 bytes) - Docker ignore patterns
- `.gitignore` (77 lines) - Git ignore patterns
- `mcp.json` (285 bytes) - MCP server configuration
- `key.json` (61 bytes) - Service account key (gitignored)

### Scripts
- `deploy_cloud_run.ps1` (13,563 bytes) - Manual Cloud Run deployment script (for local/manual deployments; CI/CD is primary method)
- `setup_scheduler.ps1` (6,995 bytes) - Manual Cloud Scheduler setup script (for one-time setup; CI/CD is primary method)

### Entry Points
- `nvidia_blog_mcp_server.py` (5,982 bytes) - MCP server entry point

### Documentation
- `README.md` (13,785 bytes) - Main project documentation

### Environment
- `.env` (5,682 bytes) - Environment variables (gitignored)

---

## Directory Structure

### `.github/`

#### Configuration
- `dependabot.yml` (34 lines) - Dependabot configuration for pip, docker, and github-actions

#### `.github/workflows/`
- `ci.yml` - Continuous Integration workflow
- `deploy.yml` - Deployment workflow
- `release.yml` - Release workflow

---

### `docs/` (8 files)

Documentation files for the project:

1. **`architecture.md`** (11,883 bytes) - System architecture documentation
2. **`ci-cd.md`** - CI/CD pipeline documentation with comprehensive troubleshooting section
3. **`deployment.md`** (4,320 bytes) - Deployment instructions (prioritizes CI/CD)
4. **`development.md`** (2,166 bytes) - Development setup guide
5. **`mcp-setup.md`** (6,766 bytes) - MCP server setup guide
6. **`security.md`** (2,919 bytes) - Security documentation
7. **`workload-identity-federation.md`** - Complete Workload Identity Federation guide (merged from workload-identity-fix.md and wif-trust-chain.md)
8. **`adding-historical-blogs.md`** (4,577 bytes) - Guide for adding historical blog posts
9. **`directory-inventory.md`** - This file (project directory inventory)

---

### `nvidia_blog_agent/` (Main Package)

The core Python package containing all application logic.

#### Core Modules (7 files)
- `__init__.py` (137 bytes) - Package initialization
- `caching.py` (3,167 bytes) - Caching utilities
- `config.py` (5,678 bytes) - Configuration management
- `monitoring.py` (9,802 bytes) - Monitoring and observability
- `rag_clients.py` (4,388 bytes) - RAG client implementations
- `retry.py` (2,989 bytes) - Retry logic utilities
- `session_manager.py` (6,638 bytes) - Session management

#### `nvidia_blog_agent/agents/` (6 files)
Agent implementations for Q&A and summarization:

- `__init__.py` (59 bytes)
- `gemini_qa_model.py` (5,426 bytes) - Gemini Q&A model wrapper
- `gemini_summarizer.py` (5,212 bytes) - Gemini summarizer wrapper
- `qa_agent.py` (4,487 bytes) - Q&A agent implementation
- `summarizer_agent.py` (7,423 bytes) - Summarizer agent implementation
- `workflow.py` (10,723 bytes) - Workflow orchestration

#### `nvidia_blog_agent/context/` (4 files)
Context management and state persistence:

- `__init__.py` (73 bytes)
- `compaction.py` (3,550 bytes) - Context compaction logic
- `session_config.py` (6,094 bytes) - Session configuration
- `state_persistence.py` (7,832 bytes) - State persistence utilities

#### `nvidia_blog_agent/contracts/` (2 files)
Data models and contracts:

- `__init__.py` (60 bytes)
- `blog_models.py` (9,218 bytes) - Blog post data models (Pydantic)

#### `nvidia_blog_agent/eval/` (2 files)
Evaluation harness:

- `__init__.py` (57 bytes)
- `harness.py` (6,562 bytes) - Evaluation harness implementation

#### `nvidia_blog_agent/tools/` (9 files)
Tool implementations for discovery, ingestion, and retrieval:

- `__init__.py` (73 bytes)
- `discovery.py` (20,720 bytes) - Blog discovery tool (largest tool file)
- `gcs_rag_ingest.py` (4,044 bytes) - GCS RAG ingestion
- `http_fetcher.py` (5,188 bytes) - HTTP content fetcher
- `rag_ingest.py` (6,509 bytes) - RAG ingestion tool
- `rag_retrieve.py` (8,791 bytes) - RAG retrieval tool
- `scraper.py` (9,911 bytes) - Web scraping utilities
- `summarization.py` (9,311 bytes) - Summarization tool
- `vertex_rag_retrieve.py` (10,301 bytes) - Vertex AI RAG retrieval

---

### `scripts/` (8 files)

Utility and test scripts:

- `__init__.py` (77 bytes)
- `import_rag_files.py` (9,600 bytes) - Import RAG files script
- `kaggle_notebook_example.py` (4,196 bytes) - Kaggle notebook example
- `run_eval_vertex.py` (9,271 bytes) - Run evaluation on Vertex AI
- `run_ingest.py` (6,405 bytes) - Run ingestion pipeline
- `run_qa.py` (5,309 bytes) - Run Q&A script
- `test_rss_feed.py` (3,599 bytes) - RSS feed testing script
- `test_service_local.py` (5,841 bytes) - Local service testing script

---

### `service/` (1 file)

FastAPI web service:

- `app.py` (26,260 bytes) - **Main FastAPI application** (largest single file)

---

### `tests/` (20 test files)

Comprehensive test suite organized by test type:

#### Root Test Files
- `conftest.py` (383 bytes) - Pytest configuration and fixtures
- `__init__.py` (41 bytes)

#### `tests/agents/` (2 files)
- `test_qa_agent.py` (8,378 bytes) - Q&A agent tests
- `test_summarizer_agent.py` (11,832 bytes) - Summarizer agent tests

#### `tests/context/` (3 files)
- `__init__.py` (49 bytes)
- `test_compaction_behavior.py` (8,594 bytes) - Context compaction tests
- `test_session_state_prefixes.py` (11,225 bytes) - Session state prefix tests

#### `tests/e2e/` (3 files)
End-to-end tests:

- `__init__.py` (25 bytes)
- `test_eval_harness_regression.py` (11,577 bytes) - Evaluation harness regression tests
- `test_full_run_smoke.py` (12,156 bytes) - Full pipeline smoke tests

#### `tests/integration/` (1 file)
Integration tests:

- `test_wif_validation.py` (9,964 bytes) - Workload Identity Federation validation tests *(untracked)*

#### `tests/unit/` (8 files)
Unit tests:

- `test_contracts.py` (16,257 bytes) - Contract/model tests (largest test file)
- `__init__.py` (19 bytes)
- `tests/unit/agents/__init__.py` (30 bytes)
- `tests/unit/tools/` (5 files):
  - `__init__.py` (29 bytes)
  - `test_discovery_tool.py` (16,650 bytes) - Discovery tool tests
  - `test_rag_ingest_payloads.py` (15,146 bytes) - RAG ingestion payload tests
  - `test_rag_retrieval_payloads.py` (14,783 bytes) - RAG retrieval payload tests
  - `test_scraper_parser.py` (15,110 bytes) - Scraper parser tests
  - `test_summarization.py` (14,351 bytes) - Summarization tests

#### `tests/workflows/` (3 files)
Workflow tests:

- `__init__.py` (41 bytes)
- `test_daily_pipeline_sequential.py` (12,446 bytes) - Daily pipeline sequential tests
- `test_parallel_scraping.py` (7,101 bytes) - Parallel scraping tests

---

## File Statistics

### Largest Files (Top 10)
1. `service/app.py` - 26,260 bytes (FastAPI application)
2. `nvidia_blog_agent/tools/discovery.py` - 20,720 bytes (Discovery tool)
3. `tests/unit/test_contracts.py` - 16,257 bytes (Contract tests)
4. `tests/unit/tools/test_discovery_tool.py` - 16,650 bytes (Discovery tool tests)
5. `tests/unit/tools/test_rag_ingest_payloads.py` - 15,146 bytes
6. `tests/unit/tools/test_scraper_parser.py` - 15,110 bytes
7. `tests/unit/tools/test_rag_retrieval_payloads.py` - 14,783 bytes
8. `tests/unit/tools/test_summarization.py` - 14,351 bytes
9. `tests/workflows/test_daily_pipeline_sequential.py` - 12,446 bytes
10. `tests/e2e/test_full_run_smoke.py` - 12,156 bytes

### File Type Breakdown
- **Python files (`.py`)**: ~60+ files
- **Markdown files (`.md`)**: 9 files (consolidated from 11)
- **Configuration files**: 
  - `toml` (pyproject.toml)
  - `json` (mcp.json, key.json)
  - `yml` (GitHub workflows, dependabot)
  - `txt` (requirements.txt)
- **PowerShell scripts (`.ps1`)**: 2 files
- **Docker files**: Dockerfile, .dockerignore

---

## Dependencies

### Core Dependencies (from `pyproject.toml`)
- `pydantic>=2.0.0,<3.0.0` - Data validation
- `httpx>=0.25.0` - HTTP client
- `beautifulsoup4>=4.12.0` - HTML parsing
- `lxml>=4.9.0` - XML/HTML parser
- `python-dateutil>=2.8.0` - Date/time handling
- `google-generativeai>=0.3.0` - Google Generative AI
- `google-cloud-storage>=2.10.0` - GCS client
- `google-cloud-aiplatform>=1.38.0` - Vertex AI client
- `fastapi>=0.104.0` - Web framework
- `uvicorn[standard]>=0.24.0` - ASGI server
- `mcp>=0.1.0` - MCP server framework
- `python-dotenv>=1.0.0` - Environment variable management
- `slowapi>=0.1.9` - Rate limiting
- `cachetools>=5.3.0` - Caching utilities
- `google-cloud-monitoring>=2.15.0` - Cloud monitoring

### Development Dependencies
- `pytest>=7.4.0` - Testing framework
- `pytest-asyncio>=0.21.0` - Async testing support

### Optional Dependencies
- `google-genai-adk>=0.1.0` - Google GenAI ADK (for Phase 4+ agents)

---

## Git Status

### Current Branch
- **Branch:** `master`
- **Status:** Up to date with `origin/master`

### Untracked Files
The following files/directories are not tracked by git:
- `tests/integration/` (directory)

**Note**: Documentation has been consolidated:
- `workload-identity-fix.md` and `wif-trust-chain.md` → merged into `workload-identity-federation.md`
- `cicd-troubleshooting.md` → merged into `ci-cd.md` as troubleshooting section

### Recent Commits
- `49ee732` - ci: Standardize on master branch only, remove main references
- `9fdf922` - docs: Add Workload Identity Federation fix guide
- `8b2f263` - Fix remaining linting errors: undefined variable and unused assignments
- `adad705` - Fix CI/CD linting and formatting issues
- `9ee0bbe` - fix: Remove session history tracking from cached responses

---

## Project Structure Summary

```
nvidia_blog_agent/
├── .github/
│   ├── dependabot.yml
│   └── workflows/
│       ├── ci.yml
│       ├── deploy.yml
│       └── release.yml
├── docs/ (10 markdown files)
├── nvidia_blog_agent/ (main package)
│   ├── agents/ (6 files)
│   ├── context/ (4 files)
│   ├── contracts/ (2 files)
│   ├── eval/ (2 files)
│   └── tools/ (9 files)
├── scripts/ (8 files)
├── service/ (1 file - app.py)
├── tests/ (20 test files)
│   ├── agents/ (2 files)
│   ├── context/ (3 files)
│   ├── e2e/ (3 files)
│   ├── integration/ (1 file - untracked)
│   ├── unit/ (8 files)
│   └── workflows/ (3 files)
├── Configuration files (root)
└── Documentation (README.md)
```

---

## Notes

- **Total Test Files:** 20 files covering unit, integration, e2e, and workflow tests
- **Main Entry Point:** `service/app.py` (FastAPI application)
- **MCP Server:** `nvidia_blog_mcp_server.py` (standalone MCP server)
- **Package Name:** `nvidia-blog-agent` (version 0.1.0)
- **Python Version:** Requires >=3.10
- **Cache Directories:** `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.egg-info/` (excluded from inventory)

---

*This inventory was generated on 2025-11-24. Update this document when significant structural changes are made to the project.*

