# Vertex AI RAG Setup Guide

This guide explains how to configure and use Vertex AI RAG Engine with the NVIDIA Blog Agent.

## Overview

Vertex AI RAG Engine provides a managed RAG solution that:
- Handles embeddings, chunking, and retrieval automatically
- Uses Vertex AI Search as the backend corpus
- Integrates seamlessly with Gemini models for grounded generation

## Architecture

```
BlogSummary → GCS Bucket → Vertex AI Search → Vertex AI RAG Engine → QAAgent
```

1. **Ingestion**: BlogSummary objects are written to GCS as text files
2. **Search Index**: Vertex AI Search ingests from GCS bucket
3. **RAG Engine**: Vertex AI RAG Engine queries Search and grounds Gemini
4. **Retrieval**: Your QAAgent queries RAG Engine for relevant documents

## Prerequisites

### 1. Enable APIs

In your GCP project (`nvidia-blog-agent`):

```bash
gcloud services enable aiplatform.googleapis.com
gcloud services enable discoveryengine.googleapis.com
```

### 2. Service Account Permissions

Your service account needs:

- **Vertex AI User** - To use RAG Engine and Gemini
- **Vertex AI Search Editor** - To manage Search data stores
- **Storage Object Admin** - To write documents to GCS

### 3. Install Dependencies

```bash
pip install google-cloud-storage google-cloud-aiplatform
```

## Setup Steps

### Step 1: Create GCS Bucket

```bash
gsutil mb -p nvidia-blog-agent -l us-central1 gs://nvidia-blog-rag-docs
```

Or via Console:
1. Go to Cloud Storage
2. Create bucket: `nvidia-blog-rag-docs`
3. Choose location: `us-central1` (or your preferred region)

### Step 2: Create Vertex AI Search Data Store

1. Go to [Vertex AI Search Console](https://console.cloud.google.com/ai/search)
2. Click "Create Data Store"
3. Choose:
   - **Data Store Type**: Unstructured data
   - **Name**: `nvidia-blog-docs`
   - **Data Source**: Cloud Storage
   - **Bucket**: `gs://nvidia-blog-rag-docs`
4. Create the data store

### Step 3: Create Search Application (Engine)

1. In Vertex AI Search Console, create a Search Application
2. Attach it to your data store
3. Note the **Engine Name** (you'll need this for RAG Engine)

### Step 4: Create Vertex AI RAG Corpus

1. Go to [Vertex AI RAG Engine Console](https://console.cloud.google.com/ai/rag)
2. Click "Create Corpus"
3. Configure:
   - **Name**: `nvidia-blog-corpus`
   - **Backend**: Vertex AI Search
   - **Search Engine**: Select your Search application from Step 3
   - **Location**: `us-central1` (must match Search location)
4. Note the **Corpus ID** (you'll use this in config)

### Step 5: Configure Environment Variables

Set these environment variables:

```bash
# Enable Vertex AI RAG
export USE_VERTEX_RAG="true"

# Vertex AI RAG Configuration
export RAG_CORPUS_ID="your-corpus-id-from-step-4"
export VERTEX_LOCATION="us-central1"
export RAG_DOCS_BUCKET="gs://nvidia-blog-rag-docs"

# Optional: Search engine name (if querying Search directly)
export RAG_SEARCH_ENGINE_NAME="projects/.../locations/.../engines/..."

# Gemini Configuration
export GEMINI_MODEL_NAME="gemini-1.5-pro"
export GEMINI_LOCATION="us-central1"

# GCP Project
export GOOGLE_CLOUD_PROJECT="nvidia-blog-agent"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

## Usage

### In Your Code

```python
from nvidia_blog_agent.config import load_config_from_env
from nvidia_blog_agent.rag_clients import create_rag_clients
from nvidia_blog_agent.agents.workflow import run_ingestion_pipeline
from nvidia_blog_agent.agents.gemini_summarizer import GeminiSummarizer

# Load configuration (will detect USE_VERTEX_RAG)
config = load_config_from_env()

# Create RAG clients (will use GCS + Vertex RAG if configured)
ingest_client, retrieve_client = create_rag_clients(config)

# Use in ingestion pipeline
summarizer = GeminiSummarizer(config.gemini)
# ... rest of pipeline setup

result = await run_ingestion_pipeline(
    feed_html=feed_html,
    existing_ids=existing_ids,
    fetcher=fetcher,
    summarizer=summarizer,
    rag_client=ingest_client,  # GcsRagIngestClient
)
```

### For QA

```python
from nvidia_blog_agent.agents.qa_agent import QAAgent
from nvidia_blog_agent.agents.gemini_qa_model import GeminiQaModel

qa_model = GeminiQaModel(config.gemini)
qa_agent = QAAgent(rag_client=retrieve_client, model=qa_model)

answer, docs = await qa_agent.answer("What did NVIDIA say about RAG?", k=5)
print(answer)
```

## How It Works

### Ingestion Flow

1. `GcsRagIngestClient.ingest_summary()` writes:
   - `{blog_id}.txt` - Document content (from `summary.to_rag_document()`)
   - `{blog_id}.metadata.json` - Metadata (title, URL, keywords, etc.)

2. Vertex AI Search automatically ingests new files from the bucket
   - You can trigger manual reimport in the Console
   - Or set up Cloud Functions to trigger on file creation

3. Documents are indexed and searchable via Vertex AI Search

### Retrieval Flow

1. `VertexRagRetrieveClient.retrieve()` queries Vertex AI RAG Engine
2. RAG Engine:
   - Queries Vertex AI Search for relevant documents
   - Retrieves document snippets and metadata
   - Returns structured results

3. Results are mapped to `RetrievedDoc` objects for use in QA

## Switching Between HTTP and Vertex RAG

The system automatically detects which backend to use based on `USE_VERTEX_RAG`:

- **HTTP RAG** (default): Set `RAG_BASE_URL` and `RAG_UUID`
- **Vertex RAG**: Set `USE_VERTEX_RAG=true` and Vertex RAG config

You can switch between them by changing environment variables - no code changes needed!

## Troubleshooting

### Documents Not Appearing in Search

1. Check GCS bucket: `gsutil ls gs://nvidia-blog-rag-docs/`
2. Trigger manual reimport in Vertex AI Search Console
3. Wait a few minutes for indexing to complete

### RAG Engine Query Fails

1. Verify corpus ID matches your RAG corpus
2. Check location matches (Search and RAG Engine must be in same region)
3. Ensure service account has Vertex AI User permissions
4. Check API is enabled: `gcloud services list --enabled`

### Import Errors

If you see import errors for `google-cloud-storage` or `google-cloud-aiplatform`:

```bash
pip install google-cloud-storage google-cloud-aiplatform
```

## Next Steps

1. Run a test ingestion with a small sample
2. Verify documents appear in Vertex AI Search Console
3. Test QA queries through your QAAgent
4. Set up automated ingestion (Cloud Scheduler + Cloud Functions)

## References

- [Vertex AI RAG Engine Documentation](https://cloud.google.com/vertex-ai/docs/generative-ai/rag)
- [Vertex AI Search Documentation](https://cloud.google.com/generative-ai-app-builder/docs)
- [GCS Python Client](https://cloud.google.com/python/docs/reference/storage/latest)

