# NVIDIA Tech Blog Intelligence Agent

A production-ready system for discovering, processing, and querying NVIDIA technical blog content using Google Cloud Platform, Vertex AI, and RAG (Retrieval-Augmented Generation).

## 🚀 Production Status

**Status**: ✅ **FULLY DEPLOYED AND OPERATIONAL**

- **Service URL**: `https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app`
- **Cloud Scheduler**: ✅ Enabled (daily at 7:00 AM ET)
- **RAG Corpus**: ✅ Active with 100+ blog posts indexed
- **Region**: `us-central1` (Cloud Run), `us-east5` (Vertex AI)
- **CI/CD**: ✅ Automated testing and deployment via GitHub Actions

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Deployment](#deployment)
- [Documentation](#documentation)
- [Contributing](#contributing)

## Overview

The NVIDIA Tech Blog Intelligence Agent is an end-to-end system that automatically:

1. **Discovers** new NVIDIA technical blog posts from RSS/Atom feeds
2. **Scrapes** and parses blog content into structured data
3. **Summarizes** posts using Google's Gemini 2.0 Flash model
4. **Ingests** summaries into a RAG backend (Vertex AI RAG Engine or HTTP-based)
5. **Answers questions** about NVIDIA blogs using RAG retrieval + Gemini 2.0 Flash

### Key Features

- ✅ **RSS/Atom Feed Support**: Automatic parsing with full content extraction
- ✅ **Dual RAG Backend**: HTTP-based or Vertex AI RAG Engine (managed)
- ✅ **Automatic Backend Detection**: Switch backends via environment variables
- ✅ **Production Ready**: Deployed to Cloud Run with automated CI/CD
- ✅ **Comprehensive Testing**: 193+ tests covering all components
- ✅ **Modular Design**: Protocol-based abstractions for easy testing and extension
- ✅ **State Management**: Session state with history tracking and compaction
- ✅ **Efficient Processing**: Uses RSS feed content directly to avoid rate limiting

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Google Cloud Project with billing enabled
- Service account with appropriate permissions (see [Deployment Guide](docs/deployment.md))

### Installation

```bash
# Clone the repository
git clone https://github.com/TomBombadil/nvidia_blog_agent.git
cd nvidia_blog_agent

# Install the package in editable mode
pip install -e .

# Or install with optional dependencies
pip install -e ".[dev,adk]"
```

### Basic Usage

1. **Set up environment variables** (see [Configuration](#configuration))

2. **Run ingestion** to process blog posts:
   ```bash
   python scripts/run_ingest.py
   ```

3. **Query the system**:
   ```bash
   python scripts/run_qa.py "What did NVIDIA say about RAG on GPUs?"
   ```

4. **Deploy to Cloud Run**:
   ```powershell
   .\deploy_cloud_run.ps1
   ```

For detailed setup instructions, see the [Development Guide](docs/development.md).

## Architecture

### System Components

```
┌─────────────────┐
│  RSS/Atom Feed  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│   Discovery     │────▶│   Scraping   │────▶│ Summarization│
└─────────────────┘     └──────────────┘     └──────┬──────┘
                                                      │
                                                      ▼
                                            ┌─────────────────┐
                                            │  RAG Ingestion  │
                                            └────────┬────────┘
                                                     │
                                                     ▼
                                            ┌─────────────────┐
                                            │  Vertex AI RAG  │
                                            │     Engine      │
                                            └────────┬────────┘
                                                     │
                                                     ▼
                                            ┌─────────────────┐
                                            │   QA Agent      │
                                            │  (Gemini 2.0)    │
                                            └─────────────────┘
```

### Core Modules

- **`contracts/`**: Pydantic data models (BlogPost, RawBlogContent, BlogSummary, RetrievedDoc)
- **`tools/`**: Discovery, scraping, summarization, and RAG operations
- **`agents/`**: Workflow orchestration, summarization, and QA agents
- **`context/`**: Session management, state prefixes, and history compaction
- **`eval/`**: Evaluation harness for testing QA performance

### RAG Backends

The system supports two RAG backend modes:

#### 1. Vertex AI RAG Engine (Recommended)

- **Managed Service**: Google handles embeddings, chunking, and retrieval
- **Vertex AI Search**: Backend search engine with hybrid search (vector + keyword)
- **Configuration**: Set `USE_VERTEX_RAG=true` and provide corpus ID
- **Benefits**: No infrastructure to manage, automatic scaling, production-ready

#### 2. HTTP-Based RAG

- **Generic HTTP Service**: Works with any HTTP-based RAG service
- **Configuration**: Set `RAG_BASE_URL` and `RAG_UUID`
- **Use Case**: Custom RAG implementations or NVIDIA CA-RAG

The system automatically detects which backend to use based on environment variables.

### Technical Specifications

- **Embedding Model**: `text-embedding-005` (Vertex AI RAG Engine)
- **Chunk Size**: 1024 tokens (configurable in Vertex AI Search)
- **Chunk Overlap**: 256 tokens (configurable in Vertex AI Search)
- **Hybrid Search**: Enabled by default (vector similarity + keyword/BM25)
- **Reranking**: Available via Vertex AI ranking API
- **QA Model**: Gemini 2.0 Flash (`gemini-2.0-flash-001`)
- **Summarization Model**: Gemini 2.0 Flash
- **Retrieval**: Recommended `top_k=8-10` for initial retrieval, top 4-6 after reranking

See [docs/architecture.md](docs/architecture.md) for complete technical details.

## Installation

### From Source

```bash
git clone https://github.com/TomBombadil/nvidia_blog_agent.git
cd nvidia_blog_agent
pip install -e .
```

### With Optional Dependencies

```bash
# Development dependencies (pytest, etc.)
pip install -e ".[dev]"

# ADK support (for Google GenAI ADK)
pip install -e ".[adk]"

# Both
pip install -e ".[dev,adk]"
```

### Google Cloud Authentication

```bash
# Set service account credentials
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# Or use Application Default Credentials
gcloud auth application-default login
```

## Configuration

Configuration is managed via environment variables. Create a `.env` file in the project root or set variables in your shell.

### Required Variables

```bash
# Google Cloud
export GOOGLE_CLOUD_PROJECT="nvidia-blog-agent"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# Gemini Configuration
export GEMINI_MODEL_NAME="gemini-2.0-flash-001"
export GEMINI_LOCATION="us-east5"
```

### Vertex AI RAG Configuration (Recommended)

```bash
export USE_VERTEX_RAG="true"
export RAG_CORPUS_ID="YOUR_CORPUS_ID"  # From Vertex AI RAG Engine
export VERTEX_LOCATION="us-east5"
export RAG_DOCS_BUCKET="gs://nvidia-blog-rag-docs"
```

### HTTP RAG Configuration (Alternative)

```bash
export RAG_BASE_URL="https://your-rag-service.run.app"
export RAG_UUID="corpus-id"
export RAG_API_KEY="optional-api-key"  # If required
```

### Optional Configuration

```bash
# State Persistence
export STATE_PATH="state.json"  # Local file (development)
# export STATE_PATH="gs://nvidia-blog-agent-state/state.json"  # GCS (production)

# Custom Feed URL (defaults to NVIDIA blog feed)
export FEED_URL="https://developer.nvidia.com/blog/feed/"
```

### Complete Configuration Example

Create a `.env` file:

```bash
# .env
GOOGLE_CLOUD_PROJECT=nvidia-blog-agent
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
GEMINI_MODEL_NAME=gemini-2.0-flash-001
GEMINI_LOCATION=us-east5
USE_VERTEX_RAG=true
RAG_CORPUS_ID=6917529027641081856
VERTEX_LOCATION=us-east5
RAG_DOCS_BUCKET=gs://nvidia-blog-rag-docs
STATE_PATH=state.json
```

**Note**: The `.env` file is automatically ignored by git. Never commit secrets or credentials.

## Usage

### Running Ingestion

Process new blog posts from the RSS feed:

```bash
# Basic usage (uses default NVIDIA blog feed)
python scripts/run_ingest.py

# Custom state file
python scripts/run_ingest.py --state-path state.json

# Use GCS for state persistence (production)
python scripts/run_ingest.py --state-path gs://nvidia-blog-agent-state/state.json

# Custom feed URL
python scripts/run_ingest.py --feed-url https://custom-blog.com/feed/

# Verbose logging
python scripts/run_ingest.py --verbose
```

**What it does:**
1. Fetches the RSS/Atom feed (default: NVIDIA Tech Blog)
2. Discovers new posts not yet processed
3. Extracts content from feed entries (or scrapes if needed)
4. Summarizes posts using Gemini 2.0 Flash
5. Ingests summaries into RAG backend
6. Updates state with processed post IDs

### Running QA Queries

Query the RAG system:

```bash
# Query via command line
python scripts/run_qa.py "What did NVIDIA say about RAG on GPUs?"

# Query via stdin
echo "What is GPU acceleration?" | python scripts/run_qa.py

# Specify number of documents to retrieve
python scripts/run_qa.py "Tell me about CUDA" --top-k 10

# Verbose logging
python scripts/run_qa.py "Question here" --verbose
```

**What it does:**
1. Retrieves relevant documents from RAG backend
2. Generates answer using Gemini 2.0 Flash
3. Displays answer with source document titles/URLs

### Programmatic Usage

```python
from nvidia_blog_agent.config import load_config_from_env
from nvidia_blog_agent.rag_clients import create_rag_clients
from nvidia_blog_agent.agents.workflow import run_ingestion_pipeline
from nvidia_blog_agent.agents.qa_agent import QAAgent
from nvidia_blog_agent.agents.gemini_qa_model import GeminiQaModel
from nvidia_blog_agent.tools.http_fetcher import fetch_feed_html

# Load configuration
config = load_config_from_env()

# Create RAG clients (automatically selects backend)
ingest_client, retrieve_client = create_rag_clients(config)

# Run ingestion
feed_html = await fetch_feed_html()
result = await run_ingestion_pipeline(
    feed_html=feed_html,
    existing_ids=set(),
    summarizer=GeminiSummarizer(config.gemini),
    rag_client=ingest_client,
)

# Query the system
qa_model = GeminiQaModel(config.gemini)
qa_agent = QAAgent(rag_client=retrieve_client, model=qa_model)
answer, docs = await qa_agent.answer("What did NVIDIA say about RAG?", k=8)
print(answer)
```

See [docs/development.md](docs/development.md) for more examples.

## API Reference

### Cloud Run HTTP API

The system includes a production-ready FastAPI service deployed to Cloud Run:

#### Endpoints

- **`GET /health`**: Health check endpoint
- **`GET /`**: Service information
- **`POST /ask`**: Answer questions using RAG
  ```json
  {
    "question": "What did NVIDIA say about RAG?",
    "top_k": 8
  }
  ```
- **`POST /ingest`**: Trigger ingestion pipeline (protected with API key)
  ```json
  {
    "feed_url": "https://developer.nvidia.com/blog/feed/",
    "api_key": "YOUR_INGEST_API_KEY"
  }
  ```

#### Example Usage

```bash
# Health check
curl https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/health

# Ask a question
curl -X POST https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is CUDA?", "top_k": 8}'

# Trigger ingestion (requires API key)
curl -X POST https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_INGEST_API_KEY" \
  -d '{"feed_url": "https://developer.nvidia.com/blog/feed/"}'
```

See [docs/deployment.md](docs/deployment.md) for deployment instructions.

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Verbose output
pytest -v

# Specific test categories
pytest tests/unit/          # Unit tests
pytest tests/workflows/      # Workflow tests
pytest tests/e2e/           # End-to-end tests

# With coverage
pytest --cov=nvidia_blog_agent --cov-report=html
```

### Test Coverage

- **193+ tests** covering all components
- **Unit tests**: Contracts, tools, agents
- **Integration tests**: Context management, state persistence
- **E2E tests**: Full pipeline, evaluation harness
- **Workflow tests**: Daily pipeline, parallel scraping

All tests should pass before submitting pull requests.

### Evaluation Harness

Test QA performance with different configurations:

```bash
# Run evaluation with default test cases
python scripts/run_eval_vertex.py

# Save results to file
python scripts/run_eval_vertex.py --output eval_results.json

# Custom test cases
python scripts/run_eval_vertex.py --cases-file my_cases.json
```

See [docs/development.md](docs/development.md) for evaluation details.

## Deployment

### Quick Deploy to Cloud Run

Deploy using the automated PowerShell script:

```powershell
# Set required environment variables
$env:RAG_CORPUS_ID = "YOUR_CORPUS_ID"
$env:INGEST_API_KEY = "YOUR_API_KEY"  # Optional, auto-generated if not provided

# Deploy
.\deploy_cloud_run.ps1
```

The script automatically:
- ✅ Creates Artifact Registry repository
- ✅ Configures IAM permissions
- ✅ Builds and pushes Docker image
- ✅ Deploys to Cloud Run
- ✅ Generates API key for `/ingest` endpoint

### CI/CD Pipeline

The project includes automated CI/CD via GitHub Actions:

- **CI Workflow**: Runs on every push/PR
  - Tests (Python 3.10, 3.11, 3.12)
  - Linting (ruff)
  - Type checking (mypy)
  - Docker build verification

- **Deploy Workflow**: Runs on pushes to `master`/`main`
  - Authenticates using Workload Identity Federation
  - Builds and pushes Docker image
  - Deploys to Cloud Run

See [docs/ci-cd.md](docs/ci-cd.md) for setup instructions.

### Cloud Scheduler

Set up daily automatic ingestion:

```powershell
# After deployment, set up scheduler
$env:SERVICE_URL = "https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app"
$env:INGEST_API_KEY = "YOUR_API_KEY"
.\setup_scheduler.ps1
```

This creates a Cloud Scheduler job that triggers ingestion daily at 7:00 AM ET.

For complete deployment instructions, see [docs/deployment.md](docs/deployment.md).

## Documentation

Comprehensive documentation is available in the `docs/` directory:

- **[deployment.md](docs/deployment.md)**: Complete deployment guide (Vertex AI RAG setup + Cloud Run)
- **[development.md](docs/development.md)**: Local development and testing guide
- **[architecture.md](docs/architecture.md)**: Technical architecture and configuration details
- **[ci-cd.md](docs/ci-cd.md)**: CI/CD pipeline setup and configuration
- **[adding-historical-blogs.md](docs/adding-historical-blogs.md)**: Guide for processing historical blog posts
- **[mcp-setup.md](docs/mcp-setup.md)**: Setting up MCP server for Cursor IDE
- **[security.md](docs/security.md)**: Security audit and best practices

## Project Structure

```
nvidia_blog_agent/
├── nvidia_blog_agent/          # Python package
│   ├── contracts/              # Data models (Pydantic)
│   ├── tools/                  # Discovery, scraping, RAG clients
│   ├── agents/                 # Workflow, summarization, QA agents
│   ├── context/                # Session state management
│   └── eval/                   # Evaluation harness
├── service/                    # Cloud Run FastAPI service
├── scripts/                    # Runtime entrypoints
├── tests/                      # Comprehensive test suite
├── docs/                       # Documentation
├── Dockerfile                  # Container image
├── pyproject.toml             # Package configuration
└── requirements.txt           # Dependencies
```

## Environment Variables Reference

### Required

- `GOOGLE_CLOUD_PROJECT`: GCP project ID
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account JSON
- `GEMINI_MODEL_NAME`: Gemini model name (e.g., "gemini-2.0-flash-001")

### Vertex AI RAG Mode

- `USE_VERTEX_RAG`: Set to "true"
- `RAG_CORPUS_ID`: Vertex AI RAG corpus ID
- `VERTEX_LOCATION`: Region (e.g., "us-east5")
- `RAG_DOCS_BUCKET`: GCS bucket for documents (e.g., "gs://nvidia-blog-rag-docs")

### HTTP RAG Mode

- `RAG_BASE_URL`: RAG service base URL
- `RAG_UUID`: Corpus identifier
- `RAG_API_KEY`: API key (if required)

### Optional

- `GEMINI_LOCATION`: Gemini model location (default: "us-east5")
- `STATE_PATH`: State file path (local JSON or `gs://bucket/blob.json`)
- `FEED_URL`: RSS/Atom feed URL (default: NVIDIA blog feed)

## Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork the repository** and create a feature branch
2. **Write tests** for new functionality
3. **Ensure all tests pass**: `pytest`
4. **Follow code style**: The project uses `ruff` for linting
5. **Update documentation** as needed
6. **Submit a pull request** with a clear description

### Development Setup

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run linter
ruff check .

# Format code
ruff format .

# Run type checker
mypy .

# Run tests
pytest -v
```

## License

[Add your license here]

## Contact

[Add your contact information here]

---

**Built with**: Python, FastAPI, Google Cloud Platform, Vertex AI, Gemini 2.0 Flash
