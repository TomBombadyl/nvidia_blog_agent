# NVIDIA Tech Blog Intelligence Agent

A production-ready system for discovering, processing, and querying NVIDIA technical blog content using Google Cloud Platform, Vertex AI, and RAG (Retrieval-Augmented Generation).

## Overview

This system provides an end-to-end pipeline that:

1. **Discovers** new NVIDIA technical blog posts from feed HTML
2. **Scrapes** and parses blog post content into structured data
3. **Summarizes** posts using Gemini LLM models
4. **Ingests** summaries into a RAG backend (HTTP-based or Vertex AI RAG Engine)
5. **Answers questions** about NVIDIA blogs using RAG retrieval + Gemini

## Architecture

The project follows a clean, modular architecture organized into phases:

### Core Components

- **Contracts** (`contracts/`): Pydantic data models (BlogPost, RawBlogContent, BlogSummary, RetrievedDoc)
- **Tools** (`tools/`): Discovery, scraping, summarization, and RAG operations
- **Agents** (`agents/`): Workflow orchestration, summarization, and QA agents
- **Context** (`context/`): Session management, state prefixes, and history compaction
- **Eval** (`eval/`): Evaluation harness for testing QA performance

### RAG Backends

The system supports **two RAG backend modes**:

#### 1. HTTP-Based RAG
- Generic HTTP RAG service (e.g., NVIDIA CA-RAG, custom Cloud Run service)
- Uses `HttpRagIngestClient` and `HttpRagRetrieveClient`
- Configured via `RAG_BASE_URL`, `RAG_UUID`, `RAG_API_KEY`

#### 2. Vertex AI RAG Engine (Recommended)
- Managed Vertex AI RAG Engine + Vertex AI Search
- Uses `GcsRagIngestClient` (writes to GCS) and `VertexRagRetrieveClient` (queries RAG Engine)
- Configured via `USE_VERTEX_RAG=true`, `RAG_CORPUS_ID`, `VERTEX_LOCATION`, `RAG_DOCS_BUCKET`
- No infrastructure to manage - Google handles embeddings, chunking, and retrieval

The system automatically detects which backend to use based on environment variables.

## Quick Start

### Prerequisites

- Python 3.10+
- Google Cloud Project with billing enabled
- Service account with appropriate permissions (see [VERTEX_RAG_SETUP.md](VERTEX_RAG_SETUP.md))

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/nvidia_blog_agent.git
cd nvidia_blog_agent

# Install dependencies
pip install -r requirements.txt

# Set up Google Cloud credentials
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

### Configuration

#### For Vertex AI RAG (Recommended)

```bash
# Gemini Configuration
export GEMINI_MODEL_NAME="gemini-1.5-pro"
export GEMINI_LOCATION="us-central1"

# Vertex AI RAG Configuration
export USE_VERTEX_RAG="true"
export RAG_CORPUS_ID="your-corpus-id"
export VERTEX_LOCATION="us-central1"
export RAG_DOCS_BUCKET="gs://nvidia-blog-rag-docs"

# GCP Project
export GOOGLE_CLOUD_PROJECT="nvidia-blog-agent"
```

See [VERTEX_RAG_SETUP.md](VERTEX_RAG_SETUP.md) for complete Vertex AI RAG setup instructions.

#### For HTTP-Based RAG

```bash
# Gemini Configuration
export GEMINI_MODEL_NAME="gemini-1.5-pro"
export GEMINI_LOCATION="us-central1"

# HTTP RAG Configuration
export RAG_BASE_URL="https://your-rag-service.run.app"
export RAG_UUID="corpus-id"
export RAG_API_KEY="optional-api-key"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test categories
pytest tests/unit/
pytest tests/workflows/
pytest tests/e2e/
```

All 182 tests should pass.

### Running Ingestion

```python
import asyncio
from nvidia_blog_agent.config import load_config_from_env
from nvidia_blog_agent.rag_clients import create_rag_clients
from nvidia_blog_agent.agents.workflow import run_ingestion_pipeline
from nvidia_blog_agent.agents.gemini_summarizer import GeminiSummarizer
from nvidia_blog_agent.context.session_config import (
    get_existing_ids_from_state,
    update_existing_ids_in_state,
    store_last_ingestion_result_metadata,
)

# Your HtmlFetcher implementation
class HttpHtmlFetcher:
    async def fetch_html(self, url: str) -> str:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text

async def main():
    config = load_config_from_env()
    ingest_client, retrieve_client = create_rag_clients(config)
    
    state = {}
    existing_ids = get_existing_ids_from_state(state)
    
    # Fetch feed HTML (your implementation)
    feed_html = "<html>...</html>"
    
    fetcher = HttpHtmlFetcher()
    summarizer = GeminiSummarizer(config.gemini)
    
    result = await run_ingestion_pipeline(
        feed_html=feed_html,
        existing_ids=existing_ids,
        fetcher=fetcher,
        summarizer=summarizer,
        rag_client=ingest_client,
    )
    
    update_existing_ids_in_state(state, result.new_posts)
    store_last_ingestion_result_metadata(state, result)
    
    print(f"Processed {len(result.summaries)} summaries")

asyncio.run(main())
```

### Running QA Queries

```python
import asyncio
from nvidia_blog_agent.config import load_config_from_env
from nvidia_blog_agent.rag_clients import create_rag_clients
from nvidia_blog_agent.agents.gemini_qa_model import GeminiQaModel
from nvidia_blog_agent.agents.qa_agent import QAAgent

async def main():
    config = load_config_from_env()
    ingest_client, retrieve_client = create_rag_clients(config)
    
    qa_model = GeminiQaModel(config.gemini)
    qa_agent = QAAgent(rag_client=retrieve_client, model=qa_model)
    
    answer, docs = await qa_agent.answer("What did NVIDIA say about RAG on GPUs?", k=5)
    
    print("Answer:", answer)
    print("Sources:", [d.title for d in docs])

asyncio.run(main())
```

## Documentation

- **[USAGE_EXAMPLE.md](USAGE_EXAMPLE.md)**: Detailed code examples for using the system
- **[VERTEX_RAG_SETUP.md](VERTEX_RAG_SETUP.md)**: Complete guide for setting up Vertex AI RAG Engine
- **[ENGINEERING_STATUS_REPORT.md](ENGINEERING_STATUS_REPORT.md)**: Comprehensive technical documentation

## Project Structure

```
nvidia_blog_agent/
├── contracts/          # Data models (BlogPost, BlogSummary, etc.)
├── tools/             # Discovery, scraping, summarization, RAG clients
├── agents/            # Workflow orchestration, summarizer, QA agent
├── context/           # Session state management and compaction
├── eval/              # Evaluation harness
├── config.py          # Configuration management
├── rag_clients.py     # RAG client factory
└── tests/             # Comprehensive test suite (182 tests)
```

## Key Features

- ✅ **Dual RAG Backend Support**: HTTP-based or Vertex AI RAG Engine
- ✅ **Automatic Backend Detection**: Switch backends via environment variables
- ✅ **Full Test Coverage**: 182 tests covering all components
- ✅ **Production Ready**: Error handling, type hints, comprehensive documentation
- ✅ **Modular Design**: Protocol-based abstractions for easy testing and extension
- ✅ **State Management**: Session state with prefixes, history, and compaction

## Environment Variables Reference

### Required for All Modes

- `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account JSON
- `GEMINI_MODEL_NAME`: Gemini model name (e.g., "gemini-1.5-pro")
- `GOOGLE_CLOUD_PROJECT`: GCP project ID

### HTTP RAG Mode

- `RAG_BASE_URL`: RAG service base URL
- `RAG_UUID`: Corpus identifier

### Vertex AI RAG Mode

- `USE_VERTEX_RAG`: Set to "true"
- `RAG_CORPUS_ID`: Vertex AI RAG corpus ID
- `VERTEX_LOCATION`: Region (e.g., "us-central1")
- `RAG_DOCS_BUCKET`: GCS bucket for documents (e.g., "gs://nvidia-blog-rag-docs")

### Optional

- `GEMINI_LOCATION`: Gemini model location
- `RAG_API_KEY`: API key for HTTP RAG (if required)
- `RAG_SEARCH_ENGINE_NAME`: Vertex AI Search engine name (if querying directly)

## Contributing

Contributions are welcome! Please ensure all tests pass before submitting a pull request.

## License

[Add your license here]

## Contact

[Add your contact information here]
