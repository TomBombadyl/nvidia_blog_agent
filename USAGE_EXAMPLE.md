# Usage Example: Configuring Real Clients

This document shows how to use the configuration and client modules to wire up real Gemini and RAG services. The system supports two RAG backend modes: HTTP-based RAG and Vertex AI RAG Engine.

## 1. Set Environment Variables

### Option A: HTTP-Based RAG

For HTTP-based RAG backends (e.g., NVIDIA CA-RAG, custom Cloud Run service):

```bash
# Gemini/LLM Configuration
export GEMINI_MODEL_NAME="gemini-1.5-pro"          # or "gemini-1.5-flash" for faster responses
export GEMINI_LOCATION="us-central1"               # Optional, depends on your deployment

# HTTP RAG Backend Configuration
export RAG_BASE_URL="https://your-rag-service.run.app"
export RAG_UUID="nvidia-blog-corpus"
export RAG_API_KEY="your-api-key"                  # Optional, if your RAG service requires auth
```

### Option B: Vertex AI RAG Engine (Recommended)

For Vertex AI RAG Engine (managed Google Cloud service):

```bash
# Gemini/LLM Configuration
export GEMINI_MODEL_NAME="gemini-1.5-pro"
export GEMINI_LOCATION="us-central1"

# Vertex AI RAG Configuration
export USE_VERTEX_RAG="true"
export RAG_CORPUS_ID="your-corpus-id"              # Vertex AI RAG corpus ID
export VERTEX_LOCATION="us-central1"               # Region for RAG/Search
export RAG_DOCS_BUCKET="gs://nvidia-blog-rag-docs" # GCS bucket for documents

# GCP Project
export GOOGLE_CLOUD_PROJECT="nvidia-blog-agent"
```

See [VERTEX_RAG_SETUP.md](VERTEX_RAG_SETUP.md) for complete Vertex AI RAG setup instructions.

## 2. Load Configuration

```python
from nvidia_blog_agent.config import load_config_from_env

# Load configuration from environment variables
# Automatically detects HTTP vs Vertex AI RAG based on USE_VERTEX_RAG
config = load_config_from_env()

# Access configuration
print(f"Using Gemini model: {config.gemini.model_name}")
if config.rag.use_vertex_rag:
    print(f"Vertex AI RAG mode: {config.rag.docs_bucket}")
else:
    print(f"HTTP RAG backend: {config.rag.base_url}")
```

## 3. Create RAG Clients

The `create_rag_clients()` function automatically creates the appropriate clients based on your configuration:

```python
from nvidia_blog_agent.config import load_config_from_env
from nvidia_blog_agent.rag_clients import create_rag_clients

config = load_config_from_env()

# Automatically selects:
# - HttpRagIngestClient + HttpRagRetrieveClient (if USE_VERTEX_RAG is not set)
# - GcsRagIngestClient + VertexRagRetrieveClient (if USE_VERTEX_RAG=true)
ingest_client, retrieve_client = create_rag_clients(config)

# Now you can use these clients in your workflow
# ingest_client.ingest_summary(summary)
# docs = await retrieve_client.retrieve("What is RAG?", k=5)
```

## 4. Create Gemini Summarizer

```python
from nvidia_blog_agent.config import load_config_from_env
from nvidia_blog_agent.agents.gemini_summarizer import GeminiSummarizer
from nvidia_blog_agent.contracts.blog_models import RawBlogContent

config = load_config_from_env()

# Create summarizer (will use GOOGLE_APPLICATION_CREDENTIALS)
summarizer = GeminiSummarizer(config.gemini)

# Use in workflow
raw_contents = [...]  # List[RawBlogContent]
summaries = await summarizer.summarize(raw_contents)
```

## 5. Create Gemini QA Model

```python
from nvidia_blog_agent.config import load_config_from_env
from nvidia_blog_agent.agents.gemini_qa_model import GeminiQaModel
from nvidia_blog_agent.agents.qa_agent import QAAgent
from nvidia_blog_agent.rag_clients import create_rag_clients

config = load_config_from_env()

# Create QA model
qa_model = GeminiQaModel(config.gemini)

# Create RAG retrieve client
_, retrieve_client = create_rag_clients(config)

# Create QA agent
qa_agent = QAAgent(rag_client=retrieve_client, model=qa_model)

# Use QA agent
answer, docs = await qa_agent.answer("What did NVIDIA say about RAG?", k=5)
print(answer)
```

## 6. Complete Ingestion Pipeline Example

```python
import asyncio
from nvidia_blog_agent.config import load_config_from_env
from nvidia_blog_agent.rag_clients import create_rag_clients
from nvidia_blog_agent.agents.gemini_summarizer import GeminiSummarizer
from nvidia_blog_agent.agents.workflow import run_ingestion_pipeline
from nvidia_blog_agent.tools.scraper import HtmlFetcher

# Your HtmlFetcher implementation (e.g., HTTP-based)
class HttpHtmlFetcher(HtmlFetcher):
    async def fetch_html(self, url: str) -> str:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text

async def main():
    # Load configuration
    config = load_config_from_env()
    
    # Create clients
    ingest_client, _ = create_rag_clients(config)
    summarizer = GeminiSummarizer(config.gemini)
    fetcher = HttpHtmlFetcher()
    
    # Run ingestion pipeline
    feed_html = "<html>...</html>"  # Your feed HTML
    existing_ids = set()  # Or load from state
    
    result = await run_ingestion_pipeline(
        feed_html=feed_html,
        existing_ids=existing_ids,
        fetcher=fetcher,
        summarizer=summarizer,
        rag_client=ingest_client,
    )
    
    print(f"Processed {len(result.summaries)} summaries")

if __name__ == "__main__":
    asyncio.run(main())
```

## 7. Authentication Setup

### For Gemini/LLM Access

1. **Create a service account** in Google Cloud Console
2. **Grant permissions**: Vertex AI User or appropriate Gemini API permissions
3. **Download credentials** as JSON file
4. **Set environment variable**:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
   ```

### For RAG Backend

- If your RAG service requires authentication, set `RAG_API_KEY` environment variable
- The `HttpRagIngestClient` and `HttpRagRetrieveClient` will automatically include the API key in the `Authorization: Bearer ...` header

## Notes

- The Gemini clients support both `google-generativeai` and `google-genai-adk` libraries
- If both are installed, ADK takes precedence
- Make sure you have the appropriate Google Cloud credentials configured
- All clients are designed to work with the existing protocol-based abstractions, making them fully testable
- The system automatically detects which RAG backend to use based on `USE_VERTEX_RAG` environment variable
- For Vertex AI RAG, documents are written to GCS and Vertex AI Search automatically ingests them
- See [VERTEX_RAG_SETUP.md](VERTEX_RAG_SETUP.md) for complete Vertex AI RAG setup instructions

