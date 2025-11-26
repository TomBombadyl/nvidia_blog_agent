# Deployment Guide

Complete guide for deploying the NVIDIA Blog Agent to Google Cloud Run with Vertex AI RAG Engine.

## Current Status

**Service URL**: `https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app`  
**Status**: ✅ Fully operational  
**Cloud Scheduler**: ✅ Enabled (daily at 7:00 AM ET)  
**RAG Corpus**: ✅ Active with 100+ documents indexed

## Part 1: Vertex AI RAG Setup

### Overview

Vertex AI RAG Engine provides a managed RAG solution that handles embeddings, chunking, and retrieval automatically using Vertex AI Search as the backend.

### Architecture

```
BlogSummary → GCS Bucket → Vertex AI Search → Vertex AI RAG Engine → QAAgent
```

### Prerequisites

1. **GCP Project** with billing enabled
2. **APIs Enabled**:
   ```bash
   gcloud services enable aiplatform.googleapis.com
   gcloud services enable discoveryengine.googleapis.com
   ```
3. **Service Account** with permissions:
   - `roles/aiplatform.user` - Vertex AI User
   - `roles/discoveryengine.editor` - Vertex AI Search Editor
   - `roles/storage.objectAdmin` - Storage Object Admin

### Step 1: Create GCS Bucket

```bash
gsutil mb -p nvidia-blog-agent -l us-east5 gs://nvidia-blog-rag-docs
```

### Step 2: Create Vertex AI Search Data Store

1. Go to [Vertex AI Search Console](https://console.cloud.google.com/ai/search)
2. Create Data Store:
   - **Type**: Unstructured data
   - **Name**: `nvidia-blog-docs`
   - **Data Source**: Cloud Storage → `gs://nvidia-blog-rag-docs`
   - **Location**: `us-east5` (must match bucket location)
3. Configure chunking:
   - **Chunk size**: `1024` tokens
   - **Chunk overlap**: `256` tokens
4. Enable hybrid search (default)

### Step 3: Create Vertex AI RAG Corpus

1. Go to [Vertex AI RAG Engine Console](https://console.cloud.google.com/vertex-ai/rag)
2. Create corpus:
   - **Name**: `nvidia-blog-corpus`
   - **Backend**: Vertex AI Search
   - **Data Store**: Select the data store from Step 2
   - **Location**: `us-east5`
3. **Save the Corpus ID** (numeric ID from resource name)

## Part 2: Cloud Run Deployment

### Recommended: Automated CI/CD Deployment

**Primary Method**: The project uses GitHub Actions for automated deployment. See [CI/CD Pipeline Documentation](ci-cd.md) for details.

**How it works**:
1. Push to `master` branch (or trigger manually via GitHub Actions UI)
2. GitHub Actions automatically:
   - Runs tests
   - Builds Docker image
   - Pushes to Artifact Registry
   - Deploys to Cloud Run
   - Performs health check

**Prerequisites**:
- GitHub secrets configured (see [CI/CD Documentation](ci-cd.md))
- Workload Identity Federation set up (see [Workload Identity Federation Guide](workload-identity-federation.md))

**Manual Trigger**:
```bash
# Via GitHub CLI
gh workflow run deploy.yml

# Or via GitHub Actions UI: Actions → Deploy to Cloud Run → Run workflow
```

### Alternative: Manual Deployment (PowerShell Scripts)

**Note**: These scripts are provided for manual deployments, local testing, or environments without CI/CD. For production, use the automated CI/CD pipeline.

**Quick Deploy**:
```powershell
$env:RAG_CORPUS_ID = "YOUR_CORPUS_ID"
.\deploy_cloud_run.ps1
```

The script automatically:
- ✅ Creates Artifact Registry repository
- ✅ Configures IAM permissions
- ✅ Builds and pushes Docker image
- ✅ Deploys to Cloud Run
- ✅ Generates and sets `INGEST_API_KEY`

**See the deployment script** (`deploy_cloud_run.ps1`) for step-by-step manual commands.

### Environment Variables and Secrets

**Secrets** (stored in Secret Manager):
- `INGEST_API_KEY` - Automatically created/retrieved from Secret Manager (`ingest-api-key`)

**Configuration** (environment variables):
- `GOOGLE_CLOUD_PROJECT=nvidia-blog-agent`
- `USE_VERTEX_RAG=true`
- `RAG_CORPUS_ID=YOUR_CORPUS_ID`
- `VERTEX_LOCATION=us-east5`
- `RAG_DOCS_BUCKET=gs://nvidia-blog-rag-docs`
- `GEMINI_MODEL_NAME=gemini-2.0-flash-001`
- `GEMINI_LOCATION=us-east5`
- `STATE_PATH=gs://nvidia-blog-agent-state/state.json`

The deployment script automatically sets up Secret Manager for `INGEST_API_KEY`. See `setup_secrets.ps1` for manual secret management.

## Part 3: Cloud Scheduler Setup

**Note**: Cloud Scheduler setup is typically a one-time operation. The scheduler job persists across deployments.

### Automated Setup (PowerShell Script)

**Note**: This script is for manual setup. Once configured, the scheduler persists and doesn't need to be re-run.

```powershell
$env:INGEST_API_KEY='YOUR_API_KEY'  # From deployment output
$env:SERVICE_URL='YOUR_SERVICE_URL'  # From deployment output
.\setup_scheduler.ps1
```

### Manual Setup

```bash
gcloud scheduler jobs create http nvidia-blog-daily-ingest \
  --location=us-central1 \
  --schedule="0 7 * * *" \
  --time-zone="America/New_York" \
  --uri="${SERVICE_URL}/ingest" \
  --http-method=POST \
  --headers="Content-Type=application/json,X-API-Key=${INGEST_API_KEY}" \
  --message-body="{}"
```

### Test Scheduler

```bash
gcloud scheduler jobs run nvidia-blog-daily-ingest \
  --location=us-central1
```

## Verification

1. **Service Health**: `curl https://YOUR_SERVICE_URL/health`
2. **Test Query**: `curl -X POST https://YOUR_SERVICE_URL/ask -H "Content-Type: application/json" -d '{"question": "What did NVIDIA say about RAG?", "top_k": 8}'`
3. **Check Logs**: `gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=nvidia-blog-agent" --limit 50`

## Troubleshooting

- **403 Errors**: Check IAM permissions and organization policies
- **Build Failures**: Verify Artifact Registry permissions
- **Deployment Issues**: Check Cloud Run logs and service account permissions

