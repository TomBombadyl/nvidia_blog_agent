# NVIDIA Tech Blog Intelligence Agent

A production-ready system for discovering, processing, and querying NVIDIA technical blog content using Google Cloud Platform, Vertex AI, and RAG (Retrieval-Augmented Generation).

## Overview

This system provides an end-to-end pipeline that:

1. **Discovers** new NVIDIA technical blog posts from RSS/Atom feed or HTML
2. **Scrapes** and parses blog post content into structured data (uses RSS feed content when available)
3. **Summarizes** posts using Gemini 2.0 Flash
4. **Ingests** summaries into a RAG backend (HTTP-based or Vertex AI RAG Engine)
5. **Answers questions** about NVIDIA blogs using RAG retrieval + Gemini 2.0 Flash

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

### Technical Specifications

- **Embedding Model**: `text-embedding-005` (used by Vertex AI RAG Engine)
- **Chunk Size**: 1024 tokens (configured in Vertex AI Search data store)
- **Chunk Overlap**: 256 tokens (configured in Vertex AI Search data store)
- **Hybrid Search**: Enabled by default (combines vector similarity + keyword/BM25)
- **Reranking**: Available via Vertex AI ranking API
- **QA Model**: Gemini 2.0 Flash
- **Summarization Model**: Gemini 2.0 Flash
- **Retrieval**: Recommended `top_k=8-10` for initial retrieval, top 4-6 after reranking (configurable)
- **Document Strategy**: One document per blog post

See [ENGINEERING_STATUS_REPORT.md](ENGINEERING_STATUS_REPORT.md) for complete technical details.

## Quick Start

### Prerequisites

- Python 3.10+
- Google Cloud Project with billing enabled
- Service account with appropriate permissions (see [CLOUD_RUN_DEPLOYMENT.md](CLOUD_RUN_DEPLOYMENT.md))

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/nvidia_blog_agent.git
cd nvidia_blog_agent

# Install the package in editable mode (recommended for development)
pip install -e .

# Or install with optional ADK support
pip install -e ".[adk]"

# Set up Google Cloud credentials
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

**Note:** The package uses modern Python packaging (`pyproject.toml`). Installing in editable mode (`-e`) makes the package importable and allows you to edit source code without reinstalling.

### Configuration

**Quick Start**: Create a `.env` file with your configuration values, or set environment variables directly in your shell.

See [SETUP_WALKTHROUGH.md](SETUP_WALKTHROUGH.md) for a complete step-by-step setup guide.

#### For Vertex AI RAG (Recommended)

```bash
# Gemini Configuration
export GEMINI_MODEL_NAME="gemini-2.0-flash-001"
export GEMINI_LOCATION="us-east5"

# Vertex AI RAG Configuration
export USE_VERTEX_RAG="true"
export RAG_CORPUS_ID="1234567890123456789"  # Your corpus ID from Vertex AI RAG Engine
export VERTEX_LOCATION="us-east5"
export RAG_DOCS_BUCKET="gs://nvidia-blog-rag-docs"

# GCP Project
export GOOGLE_CLOUD_PROJECT="nvidia-blog-agent"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# State Persistence (optional)
# Development: local file
export STATE_PATH="state.json"
# Production: GCS bucket (recommended)
# export STATE_PATH="gs://nvidia-blog-agent-state/state.json"
```

**Important**: When `USE_VERTEX_RAG=true`, the system automatically uses Vertex AI RAG Engine. Make sure you've completed the setup steps in [CLOUD_RUN_DEPLOYMENT.md](CLOUD_RUN_DEPLOYMENT.md) (Part 1: Vertex AI RAG Setup) before running ingestion or QA.

See [CLOUD_RUN_DEPLOYMENT.md](CLOUD_RUN_DEPLOYMENT.md) for complete setup and deployment instructions.

#### For HTTP-Based RAG

```bash
# Gemini Configuration
export GEMINI_MODEL_NAME="gemini-2.0-flash-001"
export GEMINI_LOCATION="us-east5"

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

Use the `run_ingest.py` script to run a complete ingestion pass:

```bash
# Basic usage (uses default state.json and NVIDIA blog RSS feed)
python scripts/run_ingest.py

# Specify custom state file
python scripts/run_ingest.py --state-path state.json

# Use GCS for state persistence
python scripts/run_ingest.py --state-path gs://nvidia-blog-agent-state/state.json

# Use custom feed URL (RSS/Atom feed or HTML page)
python scripts/run_ingest.py --feed-url https://custom-blog.com/feed/

# Enable verbose logging
python scripts/run_ingest.py --verbose
```

The script will:
1. Load configuration from environment variables
2. Load persisted state (tracks previously seen blog post IDs)
3. Fetch the NVIDIA Tech Blog RSS feed (default: `https://developer.nvidia.com/blog/feed/`)
4. Discover new posts, extract content from RSS feed when available, scrape if needed, summarize, and ingest into RAG using `run_ingestion_pipeline()`
5. Update and save state with new post IDs and ingestion metadata

**RSS Feed Support:**

The system automatically uses RSS/Atom feeds when available, which provides several benefits:
- **No 403 errors**: RSS feeds are designed for programmatic access
- **Faster processing**: Full post content is included in the feed, eliminating the need to fetch individual pages
- **More reliable**: Avoids rate limiting and blocking issues

The system supports both Atom and RSS 2.0 feed formats and automatically extracts:
- Post titles, URLs, publication dates, and categories
- Full HTML content from `<content>` tags (Atom) or `<content:encoded>` tags (RSS 2.0)
- Falls back to HTML page parsing if RSS feed is not available

**State Persistence:**

State can be stored locally or in GCS:
- **Local file**: `--state-path state.json` (default)
- **GCS**: `--state-path gs://bucket-name/state.json`
- **Environment variable**: Set `STATE_PATH` to override default

### RSS/Atom Feed Support

The system includes robust RSS and Atom feed parsing with automatic content extraction. This feature provides significant advantages over HTML page scraping:

#### Benefits

- **No 403 Errors**: RSS feeds are designed for programmatic access and don't block automated requests
- **Faster Processing**: Full post content is included in the feed, eliminating the need to fetch individual pages
- **More Reliable**: Avoids rate limiting, IP blocking, and other anti-scraping measures
- **Complete Content**: Extracts full HTML content from feed entries when available

#### Supported Formats

- **Atom Feeds**: Parses `<entry>` elements with `<content type="html">` tags
- **RSS 2.0 Feeds**: Parses `<item>` elements with `<content:encoded>` or `<description>` tags
- **HTML Fallback**: Automatically falls back to HTML page parsing if feed format is not detected

#### How It Works

1. **Feed Detection**: The system automatically detects RSS/Atom feeds by checking for XML structure
2. **Content Extraction**: Extracts full HTML content from feed entries when available
3. **Smart Fallback**: If feed content is not available, falls back to fetching individual post pages
4. **Transparent Usage**: The same API works for both RSS feeds and HTML pages

#### Testing RSS Feed Parsing

You can test RSS feed parsing with the provided test script:

```bash
# Test RSS feed parsing with the actual NVIDIA feed
python scripts/test_rss_feed.py
```

This script will:
- Fetch the RSS feed from `https://developer.nvidia.com/blog/feed/`
- Parse all posts and extract content
- Show statistics about content extraction success
- Display sample posts with content previews

#### Default Feed URL

By default, the system uses the NVIDIA Tech Blog RSS feed:
- **URL**: `https://developer.nvidia.com/blog/feed/`
- **Format**: Atom feed with full HTML content in `<content>` tags
- **Content**: All posts include complete HTML content in the feed

You can override the feed URL using the `--feed-url` parameter or by modifying the `fetch_feed_html()` function.

### Running QA Queries

Use the `run_qa.py` script to query the RAG system:

```bash
# Query via command line argument
python scripts/run_qa.py "What did NVIDIA say about RAG on GPUs?"

# Query via stdin
echo "What is GPU acceleration?" | python scripts/run_qa.py

# Specify number of documents to retrieve
python scripts/run_qa.py "Tell me about CUDA" --top-k 10

# Enable verbose logging
python scripts/run_qa.py "Question here" --verbose
```

The script will:
1. Load configuration and create RAG retrieve client (automatically selects Vertex RAG if `USE_VERTEX_RAG=true`)
2. Retrieve relevant documents from the RAG backend (recommended: top 8-10 documents initially, then top 4-6 after reranking)
3. Generate an answer using Gemini 2.0 Flash based on retrieved documents
4. Display the answer and source document titles/URLs

**Note**: The `--top-k` parameter is configurable; 8-10 is recommended for optimal retrieval quality.

## Evaluation

The system includes an evaluation harness for testing QA performance with different RAG configurations. This is useful for comparing retrieval strategies, chunk sizes, and other parameters.

### Quick Start: Using the Eval Script

The easiest way to run evaluations is using the provided script:

```bash
# Run with default test cases
python scripts/run_eval_vertex.py

# Run with verbose logging
python scripts/run_eval_vertex.py --verbose

# Save results to JSON file
python scripts/run_eval_vertex.py --output eval_results.json

# Use custom test cases from JSON file
python scripts/run_eval_vertex.py --cases-file my_cases.json
```

The script will:
1. Load your Vertex RAG configuration from environment variables
2. Create a real QA agent with Vertex RAG backend
3. Run evaluation test cases
4. Print summary statistics and detailed results
5. Optionally save results to JSON for documentation

### Programmatic Evaluation

You can also use the evaluation harness directly in your code:

```python
from nvidia_blog_agent.config import load_config_from_env
from nvidia_blog_agent.rag_clients import create_rag_clients
from nvidia_blog_agent.agents.qa_agent import QAAgent
from nvidia_blog_agent.agents.gemini_qa_model import GeminiQaModel
from nvidia_blog_agent.eval.harness import (
    EvalCase,
    run_qa_evaluation,
    summarize_eval_results
)

# Load configuration
config = load_config_from_env()

# Create RAG clients (will use Vertex RAG if configured)
_, retrieve_client = create_rag_clients(config)

# Create QA agent
qa_model = GeminiQaModel(config.gemini)
qa_agent = QAAgent(rag_client=retrieve_client, model=qa_model)

# Define evaluation cases
eval_cases = [
    EvalCase(
        question="What did NVIDIA say about RAG on GPUs?",
        expected_substrings=["RAG", "GPU"],
        max_docs=8
    ),
    EvalCase(
        question="How does CUDA acceleration work?",
        expected_substrings=["CUDA", "acceleration"],
        max_docs=10
    ),
    # Add more test cases...
]

# Run evaluation
results = await run_qa_evaluation(qa_agent, eval_cases)

# Summarize results
summary = summarize_eval_results(results)
print(f"Total cases: {summary.total}")
print(f"Passed: {summary.passed}")
print(f"Failed: {summary.failed}")
print(f"Pass rate: {summary.pass_rate:.2%}")

# Inspect individual results
for result in results:
    print(f"Question: {result.question}")
    print(f"Passed: {result.passed}")
    print(f"Answer: {result.answer[:200]}...")
    print(f"Retrieved docs: {len(result.retrieved_docs)}")
    print("---")
```

### Evaluation Use Cases

- **Compare RAG configurations**: Test different chunk sizes, embedding models, or retrieval strategies
- **Regression testing**: Ensure QA quality doesn't degrade after changes
- **A/B testing**: Compare Vertex RAG vs HTTP RAG backends
- **Parameter tuning**: Find optimal `top_k` values, reranking settings, etc.

The evaluation harness can be used to compare different RAG configurations (e.g., chunk_size changes) even though the current system uses 1024/256 as the default.

## Cloud Run HTTP API

The project includes a production-ready FastAPI service for Cloud Run deployment:

- **POST /ask**: Answer questions using RAG retrieval + Gemini QA
- **POST /ingest**: Trigger ingestion pipeline (protected with API key)
- **GET /health**: Health check endpoint

### Quick Deploy

Deploy to Cloud Run using the automated script:

```powershell
$env:RAG_CORPUS_ID = "YOUR_CORPUS_ID"
.\deploy_cloud_run.ps1
```

The script automatically handles:
- ✅ Artifact Registry setup
- ✅ IAM permissions configuration
- ✅ Docker image build and push
- ✅ Cloud Run deployment
- ✅ API key generation

See [CLOUD_RUN_DEPLOYMENT.md](CLOUD_RUN_DEPLOYMENT.md) for detailed deployment instructions and [LOCAL_TESTING.md](LOCAL_TESTING.md) for local testing.

## Documentation

- **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)**: Complete project overview and current deployment status ⭐ **START HERE**
- **[QUICK_START.md](QUICK_START.md)**: Fast path to get running locally and deployed
- **[CLOUD_RUN_DEPLOYMENT.md](CLOUD_RUN_DEPLOYMENT.md)**: Complete guide for Vertex AI RAG setup and Cloud Run deployment
- **[LOCAL_TESTING.md](LOCAL_TESTING.md)**: Guide for testing the FastAPI service locally
- **[SETUP_CLOUD_SCHEDULER.md](SETUP_CLOUD_SCHEDULER.md)**: Set up automated daily ingestion with Cloud Scheduler
- **[ENGINEERING_STATUS_REPORT.md](ENGINEERING_STATUS_REPORT.md)**: Technical details about runtime configuration and architecture

### Code Examples

#### Basic Usage

```python
from nvidia_blog_agent.config import load_config_from_env
from nvidia_blog_agent.rag_clients import create_rag_clients
from nvidia_blog_agent.agents.gemini_summarizer import GeminiSummarizer
from nvidia_blog_agent.agents.workflow import run_ingestion_pipeline
from nvidia_blog_agent.tools.http_fetcher import HttpHtmlFetcher, fetch_feed_html
from nvidia_blog_agent.context.state_persistence import load_state, save_state

# Load configuration
config = load_config_from_env()

# Create RAG clients (automatically selects HTTP or Vertex AI RAG)
ingest_client, retrieve_client = create_rag_clients(config)

# Create summarizer
summarizer = GeminiSummarizer(config.gemini)

# Fetch RSS feed (automatically uses RSS feed URL by default)
# The feed includes full post content, avoiding 403 errors
feed_html = await fetch_feed_html()  # Fetches from https://developer.nvidia.com/blog/feed/
state = load_state()
existing_ids = set()  # Or load from state

result = await run_ingestion_pipeline(
    feed_html=feed_html,
    existing_ids=existing_ids,
    fetcher=HttpHtmlFetcher(),  # Only used if RSS feed doesn't include content
    summarizer=summarizer,
    rag_client=ingest_client,
)

# Save state
save_state(state)
```

**Note**: When RSS feed content is available, the system uses it directly without fetching individual post pages. This is faster and avoids 403 errors. The `HttpHtmlFetcher` is only used as a fallback when feed content is not available.

#### QA Usage

```python
from nvidia_blog_agent.agents.qa_agent import QAAgent
from nvidia_blog_agent.agents.gemini_qa_model import GeminiQaModel

qa_model = GeminiQaModel(config.gemini)
qa_agent = QAAgent(rag_client=retrieve_client, model=qa_model)

answer, docs = await qa_agent.answer("What did NVIDIA say about RAG?", k=5)
print(answer)
print("Sources:", [d.title for d in docs])
```

See [CLOUD_RUN_DEPLOYMENT.md](CLOUD_RUN_DEPLOYMENT.md) for complete setup instructions.

## Project Structure

```
nvidia_blog_agent/                    # Project root
├── nvidia_blog_agent/               # Python package (installable)
│   ├── __init__.py
│   ├── config.py                    # Configuration management
│   ├── rag_clients.py               # RAG client factory
│   ├── contracts/                   # Data models (BlogPost, BlogSummary, etc.)
│   ├── tools/                       # Discovery, scraping, summarization, RAG clients
│   │   └── http_fetcher.py          # HTTP HTML fetcher implementation
│   ├── agents/                      # Workflow orchestration, summarizer, QA agent
│   ├── context/                     # Session state management and compaction
│   │   └── state_persistence.py     # State load/save helpers (local JSON or GCS)
│   └── eval/                        # Evaluation harness
├── service/                          # Cloud Run HTTP API service
│   └── app.py                       # FastAPI application (POST /ask, POST /ingest)
├── scripts/                          # Runtime entrypoints
│   ├── run_ingest.py                # Ingestion pipeline script
│   ├── run_qa.py                    # QA query script
│   ├── test_service_local.py        # Local service smoke tests
│   └── kaggle_notebook_example.py   # Example code for Kaggle notebooks
├── tests/                            # Comprehensive test suite (182 tests)
├── Dockerfile                        # Container image for Cloud Run
├── pyproject.toml                   # Modern Python packaging configuration
└── requirements.txt                  # Dependencies (for reference)
```

**Package Structure:** The project follows standard Python packaging conventions. The `nvidia_blog_agent/` directory is the installable package, and all source code lives within it. The project root contains scripts, tests, configuration files, and the Cloud Run service.

## Key Features

- ✅ **RSS/Atom Feed Support**: Automatic parsing of RSS and Atom feeds with full content extraction
- ✅ **Dual RAG Backend Support**: HTTP-based or Vertex AI RAG Engine
- ✅ **Automatic Backend Detection**: Switch backends via environment variables
- ✅ **Full Test Coverage**: 182+ tests covering all components
- ✅ **Production Ready**: Error handling, type hints, comprehensive documentation
- ✅ **Modular Design**: Protocol-based abstractions for easy testing and extension
- ✅ **State Management**: Session state with prefixes, history, and compaction
- ✅ **Efficient Content Extraction**: Uses RSS feed content directly to avoid 403 errors and improve performance

## Environment Variables Reference

### Required for All Modes

- `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account JSON
- `GEMINI_MODEL_NAME`: Gemini model name (e.g., "gemini-2.0-flash-001")
- `GOOGLE_CLOUD_PROJECT`: GCP project ID

### HTTP RAG Mode

- `RAG_BASE_URL`: RAG service base URL
- `RAG_UUID`: Corpus identifier

### Vertex AI RAG Mode

- `USE_VERTEX_RAG`: Set to "true"
- `RAG_CORPUS_ID`: Vertex AI RAG corpus ID
- `VERTEX_LOCATION`: Region (e.g., "us-east5" for Columbus)
- `RAG_DOCS_BUCKET`: GCS bucket for documents (e.g., "gs://nvidia-blog-rag-docs")

### Optional

- `GEMINI_LOCATION`: Gemini model location
- `RAG_API_KEY`: API key for HTTP RAG (if required)
- `RAG_SEARCH_ENGINE_NAME`: Vertex AI Search serving config resource name (if querying directly)
- `STATE_PATH`: Path to state file (local JSON or `gs://bucket/blob.json`). Defaults to `state.json`
  - **Development**: `state.json` (local file)
  - **Production**: `gs://nvidia-blog-agent-state/state.json` (GCS bucket, recommended)

## Contributing

Contributions are welcome! Please ensure all tests pass before submitting a pull request.

## License

[Add your license here]

## Contact

[Add your contact information here]
