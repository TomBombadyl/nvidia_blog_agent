# Setup and Deployment Guide

This guide provides complete instructions for setting up Vertex AI RAG Engine and deploying the NVIDIA Blog Agent to Google Cloud Run.

## 🎉 Current Status: PRODUCTION DEPLOYED

**Service URL**: `https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app`  
**Status**: ✅ Fully operational  
**Cloud Scheduler**: ✅ Enabled (daily at 7:00 AM ET)  
**RAG Corpus**: ✅ Active with 100+ documents indexed

For complete project overview, see [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md).

## Overview

This guide covers:
1. **Vertex AI RAG Setup**: Configure Vertex AI RAG Engine, Search, and GCS for document storage
2. **Cloud Run Deployment**: Deploy the FastAPI service to Cloud Run with proper security and configuration
3. **Operations Setup**: Configure API keys, Cloud Scheduler, and MCP server

The Cloud Run service provides two main endpoints:
- **POST /ask**: Answer questions using RAG retrieval + Gemini QA
- **POST /ingest**: Trigger ingestion pipeline to discover and ingest new blog posts

---

## Part 1: Vertex AI RAG Setup

### Overview

Vertex AI RAG Engine provides a managed RAG solution that:
- Handles embeddings, chunking, and retrieval automatically
- Uses Vertex AI Search as the backend corpus
- Integrates seamlessly with Gemini models for grounded generation

### Architecture

```
BlogSummary → GCS Bucket → Vertex AI Search → Vertex AI RAG Engine → QAAgent
```

1. **Ingestion**: BlogSummary objects are written to GCS as text files
2. **Search Index**: Vertex AI Search ingests from GCS bucket
3. **RAG Engine**: Vertex AI RAG Engine queries Search and grounds Gemini
4. **Retrieval**: Your QAAgent queries RAG Engine for relevant documents

### Prerequisites

1. **GCP Project**: `nvidia-blog-agent` (or your project ID)
2. **APIs Enabled**:
   ```bash
   gcloud services enable aiplatform.googleapis.com
   gcloud services enable discoveryengine.googleapis.com
   ```
3. **Service Account Permissions**:
   - **Vertex AI User** - To use RAG Engine and Gemini
   - **Vertex AI Search Editor** - To manage Search data stores
   - **Storage Object Admin** - To write documents to GCS
4. **Dependencies**:
   ```bash
   pip install google-cloud-storage google-cloud-aiplatform
   ```

### Step 1: Create GCS Bucket

```bash
gsutil mb -p nvidia-blog-agent -l us-east5 gs://nvidia-blog-rag-docs
```

Or via Console:
1. Go to Cloud Storage
2. Create bucket: `nvidia-blog-rag-docs`
3. Choose location: `us-east5` (Columbus) - must match your Vertex AI region

### Step 2: Create Vertex AI Search Data Store

1. Go to [Vertex AI Search Console](https://console.cloud.google.com/ai/search)
2. Click "Create Data Store"
3. Choose:
   - **Data Store Type**: Unstructured data
   - **Name**: `nvidia-blog-docs`
   - **Data Source**: Cloud Storage
   - **Bucket**: `gs://nvidia-blog-rag-docs`
   - **Synchronization frequency**: Choose based on your needs (e.g., "On demand" or "Daily")
4. In **Document Processing Options** (expand this section):
   - **Chunking**: Configure custom chunking
     - **Chunk size**: `1024` tokens
     - **Chunk overlap**: `256` tokens
   - **Parsing**: Enable parsing for unstructured documents (PDF, HTML, TXT)
5. Select **Location**: `us-east5` (Columbus) - must match your bucket location
6. Click **Create**

**Note**: The data store will automatically enable hybrid search (vector + keyword/BM25) by default. This provides the best retrieval performance.

**Important**: Chunking is configured in the Vertex AI Search data store settings (Step 2). These settings apply to all documents ingested into the Search data store, which is then used by the RAG Engine.

### Step 3: Create Search Application (Engine)

1. In Vertex AI Search Console, create a **Search Application**
2. Attach it to your data store (`nvidia-blog-docs`)
3. Configure search settings:
   - **Enable hybrid search**: Already enabled by default (combines vector similarity and keyword/BM25 search)
   - **Enable reranking**: Recommended for better relevance (uses Vertex AI ranking API)
4. Note the **Serving Config resource name** in the format:
   ```
   projects/nvidia-blog-agent/locations/us-east5/collections/default_collection/dataStores/nvidia-blog-docs/servingConfigs/default_search
   ```
   Or if using an engine:
   ```
   projects/nvidia-blog-agent/locations/us-east5/collections/default_collection/engines/{engine_id}/servingConfigs/{serving_config_id}
   ```
   You'll need this for the RAG corpus configuration.

### Step 4: Create Vertex AI RAG Corpus

1. Go to [Vertex AI RAG Engine Console](https://console.cloud.google.com/ai/rag)
2. Click "Create Corpus"
3. Configure:
   - **Name**: `nvidia-blog-corpus`
   - **Description**: "NVIDIA Tech Blog corpus for RAG"
   - **Backend**: Vertex AI Search
   - **Vertex AI Search Serving Config**: Paste the serving config resource name from Step 3
     - Format: `projects/nvidia-blog-agent/locations/us-east5/collections/default_collection/dataStores/nvidia-blog-docs/servingConfigs/default_search`
   - **Location**: `us-east5` (Columbus) - must match Search location
   - **Embedding Model**: `text-embedding-005` (default and recommended)
     - This is the best available embedding model for RAG
     - Uses full/default embedding dimension (high quality)
     - Endpoint: `publishers/google/models/text-embedding-005`
4. Click **Create**
5. Note the **Corpus ID** from the corpus resource name:
   - Format: `projects/nvidia-blog-agent/locations/us-east5/ragCorpora/{corpus_id}`
   - Copy just the numeric `{corpus_id}` part for use in environment variables

**Important Configuration Notes**:
- **Embedding Model**: `text-embedding-005` is the default and recommended model. It provides high-quality embeddings with full dimension support.
- **Hybrid Search**: Enabled automatically when using Vertex AI Search as backend (combines vector similarity with keyword/BM25 search).
- **Reranking**: Can be enabled via retrieval configuration for improved relevance.
- **Chunking**: Configured in Step 2 (1024 tokens with 256 token overlap) - this applies to documents ingested into the Search data store.

### Step 5: Configure Environment Variables

Set these environment variables for local development and testing:

```bash
# Enable Vertex AI RAG
export USE_VERTEX_RAG="true"

# Vertex AI RAG Configuration
export RAG_CORPUS_ID="1234567890123456789"  # Your corpus ID from Step 4 (numeric ID only)
export VERTEX_LOCATION="us-east5"
export RAG_DOCS_BUCKET="gs://nvidia-blog-rag-docs"

# Optional: Search engine serving config (if querying Search directly)
# Format: projects/{project}/locations/{location}/collections/{collection}/dataStores/{data_store}/servingConfigs/{serving_config}
export RAG_SEARCH_ENGINE_NAME="projects/nvidia-blog-agent/locations/us-east5/collections/default_collection/dataStores/nvidia-blog-docs/servingConfigs/default_search"

# Gemini Configuration
export GEMINI_MODEL_NAME="gemini-2.0-flash-001"
export GEMINI_LOCATION="us-east5"

# GCP Project
export GOOGLE_CLOUD_PROJECT="nvidia-blog-agent"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# State Persistence (optional, but recommended for production)
# Development: local JSON file
export STATE_PATH="state.json"
# Production: GCS bucket
# export STATE_PATH="gs://nvidia-blog-agent-state/state.json"
```

**Environment Variable Reference**:
- `USE_VERTEX_RAG`: Must be set to `"true"` (case-insensitive) to enable Vertex AI RAG
- `RAG_CORPUS_ID`: The numeric corpus ID from Step 4 (not the full resource name)
- `VERTEX_LOCATION`: Region where your RAG corpus and Search data store are located
- `RAG_DOCS_BUCKET`: GCS bucket where documents are stored (must match Step 1)
- `STATE_PATH`: Path for state persistence (local file or GCS URI)

### How Vertex AI RAG Works

#### Ingestion Flow

1. `GcsRagIngestClient.ingest_summary()` writes to GCS:
   - `{blog_id}.txt` - Document content (from `summary.to_rag_document()`)
   - `{blog_id}.metadata.json` - Metadata (title, URL, keywords, etc.)

2. Vertex AI Search automatically ingests new files from the bucket:
   - Documents are chunked according to Step 2 configuration (1024 tokens, 256 overlap)
   - Embeddings are generated using `text-embedding-005` model
   - Documents are indexed with hybrid search enabled (vector + keyword/BM25)
   - You can trigger manual reimport in the Console if needed

3. Documents are searchable via Vertex AI Search and accessible through RAG Engine

#### Retrieval Flow

1. `VertexRagRetrieveClient.retrieve()` queries Vertex AI RAG Engine with:
   - Query text
   - `top_k` parameter (configurable; 8-10 is recommended for initial retrieval)

2. RAG Engine:
   - Uses hybrid search (vector similarity + keyword/BM25) to find relevant documents
   - Optionally applies reranking for better relevance ordering
   - Retrieves document snippets and metadata from Vertex AI Search
   - Returns structured results with scores

3. Results are mapped to `RetrievedDoc` objects for use in QA
4. QA agent uses retrieved documents (typically top 4-6 after reranking, but configurable via `k` parameter) to generate grounded answers with Gemini 1.5 Pro

#### Retrieval Configuration

The system is configured for optimal retrieval:
- **Initial retrieval**: `top_k=8-10` documents (recommended range, configurable)
- **After reranking**: Top 4-6 documents passed to Gemini (recommended range, configurable)
- **Hybrid search**: Enabled (combines semantic and keyword matching)
- **Reranking**: Can be enabled via Vertex AI ranking API for improved relevance
- **Embedding model**: `text-embedding-005` (high-quality, full-dimension embeddings)

**Note**: The `top_k` parameter is configurable when calling the retrieval API. The ranges above are recommendations based on testing for optimal performance.

### Vertex AI RAG Troubleshooting

#### Documents Not Appearing in Search

1. Check GCS bucket: `gsutil ls gs://nvidia-blog-rag-docs/`
2. Trigger manual reimport in Vertex AI Search Console
3. Wait a few minutes for indexing to complete

#### RAG Engine Query Fails

1. Verify corpus ID matches your RAG corpus
2. Check location matches (Search and RAG Engine must be in same region)
3. Ensure service account has Vertex AI User permissions
4. Check API is enabled: `gcloud services list --enabled`

#### Import Errors

If you see import errors for `google-cloud-storage` or `google-cloud-aiplatform`:

```bash
pip install google-cloud-storage google-cloud-aiplatform
```

---

## Part 2: Cloud Run Deployment

### Prerequisites

Before deploying to Cloud Run, ensure you have:
1. ✅ Completed Part 1: Vertex AI RAG Setup
2. ✅ Your RAG corpus ID from Part 1, Step 4
3. ✅ GCP Project with billing enabled
4. ✅ Additional APIs enabled:
   ```bash
   gcloud services enable run.googleapis.com
   gcloud services enable cloudbuild.googleapis.com
   gcloud services enable containerregistry.googleapis.com  # or artifactregistry.googleapis.com
   ```

**Technical Note**: The deployment uses Vertex AI RAG Engine with `text-embedding-005` embeddings and hybrid search. Chunking (1024 tokens, 256 overlap) is configured in your Vertex AI Search data store. See [ENGINEERING_STATUS_REPORT.md](ENGINEERING_STATUS_REPORT.md) for technical details.

### Step 1: Create Service Account for Cloud Run

Create a dedicated service account for the Cloud Run service with minimal required permissions:

```bash
# Set your project ID
export PROJECT_ID="nvidia-blog-agent"

# Create service account
gcloud iam service-accounts create nvidia-blog-agent-sa \
    --display-name="NVIDIA Blog Agent Cloud Run Service Account" \
    --project=$PROJECT_ID

# Grant minimal required roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:nvidia-blog-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:nvidia-blog-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"

# Note: Vertex AI Search permissions are typically included in aiplatform.user
# If you need explicit Search permissions, add:
# --role="roles/discoveryengine.viewer"
```

**Security Best Practice**: The service account uses Application Default Credentials (ADC) in Cloud Run. No JSON keys are needed or should be stored in the container.

### Step 2: Create GCS Bucket for State

If you haven't already created the state bucket:

```bash
# Create bucket for state persistence
gsutil mb -p $PROJECT_ID -l us-east5 gs://nvidia-blog-agent-state

# Grant service account access to the bucket
gsutil iam ch \
    serviceAccount:nvidia-blog-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com:objectAdmin \
    gs://nvidia-blog-agent-state
```

### Step 3: Deploy Using Automated Script (Recommended)

The easiest way to deploy is using the automated PowerShell script:

```powershell
# Set your RAG corpus ID
$env:RAG_CORPUS_ID = "YOUR_CORPUS_ID"

# Run the deployment script
.\deploy_cloud_run.ps1
```

The script automatically:
- ✅ Creates Artifact Registry repository if needed
- ✅ Configures all required IAM permissions (Cloud Build, Compute Engine, Artifact Registry)
- ✅ Builds and pushes the Docker image using Cloud Build
- ✅ Deploys to Cloud Run with all environment variables
- ✅ Handles retries and error recovery

**Note**: The script uses Artifact Registry (not GCR) and handles all permission setup automatically.

### Step 4: Manual Deployment (Alternative)

If you prefer manual deployment or need to customize the process:

#### Build and Push Container Image

```bash
# Create Artifact Registry repository (if not exists)
gcloud artifacts repositories create nvidia-blog-agent \
    --repository-format=docker \
    --location=us-central1 \
    --project=$PROJECT_ID

# Build and push using Cloud Build
gcloud builds submit --tag us-central1-docker.pkg.dev/$PROJECT_ID/nvidia-blog-agent/nvidia-blog-agent:latest
```

#### Deploy to Cloud Run

Deploy the service with proper configuration:

```bash
# Deploy to Cloud Run
gcloud run deploy nvidia-blog-agent \
    --image us-central1-docker.pkg.dev/$PROJECT_ID/nvidia-blog-agent/nvidia-blog-agent:latest \
    --platform managed \
    --region us-central1 \
    --service-account nvidia-blog-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --max-instances 10 \
    --min-instances 0 \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
    --set-env-vars "USE_VERTEX_RAG=true" \
    --set-env-vars "RAG_CORPUS_ID=YOUR_CORPUS_ID" \
    --set-env-vars "VERTEX_LOCATION=us-east5" \
    --set-env-vars "RAG_DOCS_BUCKET=gs://nvidia-blog-rag-docs" \
    --set-env-vars "STATE_PATH=gs://nvidia-blog-agent-state/state.json" \
    --set-env-vars "GEMINI_MODEL_NAME=gemini-2.0-flash-001" \
    --set-env-vars "GEMINI_LOCATION=us-east5" \
    --project $PROJECT_ID
```

**Note**: If you see an IAM policy warning about `allUsers`, your organization policy may restrict public access. The service is still deployed and functional, but requests may require authentication.

**Important**: Replace `YOUR_CORPUS_ID` with your actual Vertex AI RAG corpus ID from Part 1, Step 4.

### Step 5: Verify Deployment

#### Test the Health Endpoint

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe nvidia-blog-agent \
    --region us-central1 \
    --format 'value(status.url)' \
    --project $PROJECT_ID)

# Test health endpoint (may require authentication if org policy restricts public access)
curl $SERVICE_URL/health
```

**Note**: If you get `403 Forbidden`, your organization policy may require authentication. The service is deployed and working - you'll need to authenticate requests using `gcloud auth print-identity-token` or service account credentials.

#### Test the /ask Endpoint

```bash
# Test QA endpoint
curl -X POST $SERVICE_URL/ask \
    -H "Content-Type: application/json" \
    -d '{
        "question": "What did NVIDIA say about RAG on GPUs?",
        "top_k": 5
    }'
```

#### Test the /ingest Endpoint

```bash
# Test ingestion endpoint (requires API key)
curl -X POST $SERVICE_URL/ingest \
    -H "Content-Type: application/json" \
    -H "X-API-Key: your-secret-api-key-here" \
    -d '{}'
```

## Configuration Reference

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | `nvidia-blog-agent` |
| `USE_VERTEX_RAG` | Enable Vertex AI RAG | `true` |
| `RAG_CORPUS_ID` | Vertex AI RAG corpus ID | `1234567890123456789` |
| `VERTEX_LOCATION` | Vertex AI region | `us-east5` (Columbus) |
| `RAG_DOCS_BUCKET` | GCS bucket for documents | `gs://nvidia-blog-rag-docs` |
| `STATE_PATH` | State persistence path | `gs://nvidia-blog-agent-state/state.json` |
| `GEMINI_MODEL_NAME` | Gemini model name | `gemini-2.0-flash-001` |
| `GEMINI_LOCATION` | Gemini region | `us-east5` (Columbus) |

### Optional Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `INGEST_API_KEY` | API key for /ingest protection | (set via Secret Manager) |
| `RAG_SEARCH_ENGINE_NAME` | Vertex AI Search serving config | (optional) |

## Security Best Practices

### 1. Service Account Permissions

The service account should have **minimal required permissions**:
- `roles/aiplatform.user`: For Vertex AI RAG Engine and Gemini API
- `roles/storage.objectAdmin`: For GCS bucket access (state and documents)

**Do NOT** grant overly broad roles like `roles/owner` or `roles/editor`.

### 2. Authentication

- **Public Endpoints**: `/ask` and `/health` are public (suitable for capstone demo)
- **Protected Endpoint**: `/ingest` can be protected with API key via Secret Manager
- **Future Enhancement**: Consider using Cloud Endpoints or API Gateway for rate limiting and authentication

### 3. Secrets Management

- **Never** hardcode secrets in environment variables
- Use **Secret Manager** for sensitive values (e.g., `INGEST_API_KEY`)
- Service account automatically has access to secrets via IAM

### 4. Network Security

- Cloud Run services are accessible via HTTPS by default
- Consider VPC connector if you need private network access
- Use Cloud Armor for DDoS protection if needed

### 5. Resource Limits

- Set appropriate memory and CPU limits (2Gi memory, 2 CPU recommended)
- Set `max-instances` to prevent cost overruns
- Use `min-instances=0` for cost optimization (cold starts acceptable)

## Monitoring and Logging

### View Logs

```bash
# View recent logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=nvidia-blog-agent" \
    --limit 50 \
    --project $PROJECT_ID

# Follow logs in real-time
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=nvidia-blog-agent" \
    --project $PROJECT_ID
```

### Set Up Alerts

Create alerting policies in Cloud Monitoring for:
- High error rates
- High latency
- Service unavailability

## Cost Optimization

1. **Min Instances**: Set `min-instances=0` to allow scaling to zero
2. **Max Instances**: Set reasonable `max-instances` (e.g., 10) to prevent cost overruns
3. **Memory/CPU**: Right-size based on actual usage (start with 2Gi/2 CPU)
4. **Timeout**: Set appropriate timeout (300s for ingestion, can be lower for /ask)

## Troubleshooting

### Service Won't Start

1. Check logs: `gcloud logging read ...`
2. Verify service account permissions
3. Verify environment variables are set correctly
4. Check that Vertex AI RAG corpus exists and is accessible (from Part 1)

### Authentication Errors

1. Verify service account has correct IAM roles
2. Check that Application Default Credentials are working (automatic in Cloud Run)
3. Verify project ID is correct

### RAG Retrieval Fails

1. Verify `RAG_CORPUS_ID` is correct (from Part 1, Step 4)
2. Check that corpus is in the same region as `VERTEX_LOCATION`
3. Verify documents are ingested in the GCS bucket
4. Check Vertex AI Search data store is synced

---

## Part 3: Operations Setup

### Step 1: Create and Configure Ingest API Key

Create a strong random API key for protecting the `/ingest` endpoint:

```bash
export PROJECT_ID="nvidia-blog-agent"
export INGEST_KEY="your-very-strong-random-key"  # Generate a secure random string

# Create Secret in Secret Manager
echo -n "$INGEST_KEY" | gcloud secrets create ingest-api-key \
  --data-file=- \
  --project=$PROJECT_ID

# Grant Cloud Run service account access to the secret
gcloud secrets add-iam-policy-binding ingest-api-key \
  --member="serviceAccount:nvidia-blog-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=$PROJECT_ID
```

**Important**: Save the `INGEST_KEY` value securely - you'll need it for Cloud Scheduler and the MCP server.

### Step 2: Update Cloud Run Deployment with API Key

When deploying or updating Cloud Run, inject the secret as an environment variable:

```bash
gcloud run deploy nvidia-blog-agent \
  --image gcr.io/$PROJECT_ID/nvidia-blog-agent:latest \
  --platform managed \
  --region us-central1 \
  --service-account nvidia-blog-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --min-instances 0 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
  --set-env-vars "USE_VERTEX_RAG=true" \
  --set-env-vars "RAG_CORPUS_ID=YOUR_CORPUS_ID" \
    --set-env-vars "VERTEX_LOCATION=us-east5" \
    --set-env-vars "RAG_DOCS_BUCKET=gs://nvidia-blog-rag-docs" \
    --set-env-vars "STATE_PATH=gs://nvidia-blog-agent-state/state.json" \
    --set-env-vars "GEMINI_MODEL_NAME=gemini-2.0-flash-001" \
    --set-env-vars "GEMINI_LOCATION=us-east5" \
  --set-secrets "INGEST_API_KEY=ingest-api-key:latest" \
  --project $PROJECT_ID
```

### Step 3: Set Up Cloud Scheduler for Daily Ingestion

Configure automatic daily ingestion at 7:00 AM US/Eastern:

```bash
# Get the Cloud Run service URL
SERVICE_URL=$(gcloud run services describe nvidia-blog-agent \
  --region us-central1 \
  --format='value(status.url)' \
  --project $PROJECT_ID)

echo "Service URL: $SERVICE_URL"

# Create Cloud Scheduler job
gcloud scheduler jobs create http nvidia-blog-daily-ingest \
  --project=$PROJECT_ID \
  --location=us-central1 \
  --schedule="0 7 * * *" \
  --time-zone="America/New_York" \
  --uri="${SERVICE_URL}/ingest" \
  --http-method=POST \
  --headers="Content-Type=application/json,X-API-Key=${INGEST_KEY}" \
  --body="{}"
```

**Schedule Details**:
- **Cron**: `0 7 * * *` (7:00 AM daily)
- **Time Zone**: `America/New_York` (US/Eastern)
- **Endpoint**: `/ingest` with API key protection

To test the scheduler job manually:

```bash
gcloud scheduler jobs run nvidia-blog-daily-ingest \
  --location=us-central1 \
  --project=$PROJECT_ID
```

### Step 4: Set Up MCP Server (Optional)

The MCP server provides a stdio-based interface for MCP-capable hosts to interact with the Cloud Run service.

#### 4.1. Install Dependencies

```bash
pip install "mcp>=0.1.0" httpx python-dotenv
```

#### 4.2. Configure Environment Variables

Set these in your `.env` file or environment:

```bash
export NVIDIA_BLOG_SERVICE_URL="https://YOUR-CLOUD-RUN-URL"
export INGEST_API_KEY="$INGEST_KEY"  # Same value as Secret Manager
```

#### 4.3. Run the MCP Server

```bash
python nvidia_blog_mcp_server.py
```

The server runs over stdio and can be connected by any MCP-capable host (Cursor, Claude Desktop, ADK's MCPToolset, etc.).

#### 4.4. MCP Tools

The server exposes two tools:

1. **ask_nvidia_blog** (read-only)
   - Query the RAG system with questions about NVIDIA blogs
   - Parameters: `question` (required), `top_k` (optional, default 8)

2. **trigger_ingest** (write)
   - Trigger a new ingestion run
   - Uses the protected `/ingest` endpoint with API key
   - Parameters: `force` (optional, currently ignored)

#### 4.5. MCP Manifest

The `mcp.json` file in the repo root provides the manifest for MCP hosts. Point your MCP host to this file or configure it directly in your host's settings.

## Next Steps

1. **Set up CI/CD**: Use Cloud Build triggers to auto-deploy on git push
2. **Add Monitoring**: Set up dashboards and alerts in Cloud Monitoring
3. **Rate Limiting**: Consider Cloud Endpoints or API Gateway for rate limiting
4. **Custom Domain**: Map a custom domain to the Cloud Run service
5. **Caching**: Consider adding Redis for caching frequent queries
6. **Automated Ingestion**: Cloud Scheduler is already configured (see Part 3, Step 3)

## References

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Run Best Practices](https://cloud.google.com/run/docs/tips)
- [Vertex AI RAG Engine Documentation](https://cloud.google.com/vertex-ai/docs/generative-ai/rag)
- [Vertex AI Search Documentation](https://cloud.google.com/generative-ai-app-builder/docs)
- [Engineering Status Report](ENGINEERING_STATUS_REPORT.md)
