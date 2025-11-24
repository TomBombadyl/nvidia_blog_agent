# Cloud Run Deployment Guide

This guide explains how to deploy the NVIDIA Blog Agent as a public-facing HTTP service on Google Cloud Run.

## Overview

The Cloud Run service provides two main endpoints:
- **POST /ask**: Answer questions using RAG retrieval + Gemini QA
- **POST /ingest**: Trigger ingestion pipeline to discover and ingest new blog posts

The service is containerized using Docker and follows Google Cloud best practices for security, IAM, and service accounts.

## Prerequisites

1. **GCP Project**: `nvidia-blog-agent` (or your project ID)
2. **APIs Enabled**:
   - Cloud Run API
   - Cloud Build API
   - Container Registry API (or Artifact Registry API)
   - Vertex AI API
   - Discovery Engine API (Vertex AI Search)
   - Cloud Storage API
3. **Vertex AI RAG Setup**: Complete the setup in [VERTEX_RAG_SETUP.md](VERTEX_RAG_SETUP.md)
4. **Service Account**: Dedicated service account for Cloud Run (see below)

## Step 1: Create Service Account

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

## Step 2: Create GCS Bucket for State (if not exists)

If you haven't already created the state bucket:

```bash
# Create bucket for state persistence
gsutil mb -p $PROJECT_ID -l us-central1 gs://nvidia-blog-agent-state

# Grant service account access to the bucket
gsutil iam ch \
    serviceAccount:nvidia-blog-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com:objectAdmin \
    gs://nvidia-blog-agent-state
```

## Step 3: Build and Push Container Image

### Option A: Using Cloud Build (Recommended)

```bash
# Build and push using Cloud Build
gcloud builds submit --tag gcr.io/$PROJECT_ID/nvidia-blog-agent:latest

# Or use Artifact Registry (recommended for new projects)
# First, create an Artifact Registry repository:
gcloud artifacts repositories create nvidia-blog-agent \
    --repository-format=docker \
    --location=us-central1 \
    --project=$PROJECT_ID

# Then build and push:
gcloud builds submit --tag us-central1-docker.pkg.dev/$PROJECT_ID/nvidia-blog-agent/nvidia-blog-agent:latest
```

### Option B: Build Locally and Push

```bash
# Build locally
docker build -t gcr.io/$PROJECT_ID/nvidia-blog-agent:latest .

# Authenticate Docker
gcloud auth configure-docker

# Push to Container Registry
docker push gcr.io/$PROJECT_ID/nvidia-blog-agent:latest

# Or push to Artifact Registry
docker tag gcr.io/$PROJECT_ID/nvidia-blog-agent:latest \
    us-central1-docker.pkg.dev/$PROJECT_ID/nvidia-blog-agent/nvidia-blog-agent:latest
docker push us-central1-docker.pkg.dev/$PROJECT_ID/nvidia-blog-agent/nvidia-blog-agent:latest
```

## Step 4: Deploy to Cloud Run

Deploy the service with proper configuration:

```bash
# Deploy to Cloud Run
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
    --set-env-vars "VERTEX_LOCATION=us-central1" \
    --set-env-vars "RAG_DOCS_BUCKET=gs://nvidia-blog-rag-docs" \
    --set-env-vars "STATE_PATH=gs://nvidia-blog-agent-state/state.json" \
    --set-env-vars "GEMINI_MODEL_NAME=gemini-1.5-pro" \
    --set-env-vars "GEMINI_LOCATION=us-central1" \
    --project $PROJECT_ID
```

**Important**: Replace `YOUR_CORPUS_ID` with your actual Vertex AI RAG corpus ID.

### Optional: Protect /ingest Endpoint with API Key

If you want to protect the `/ingest` endpoint, use Secret Manager:

```bash
# Create a secret for the API key
echo -n "your-secret-api-key-here" | gcloud secrets create ingest-api-key \
    --data-file=- \
    --project=$PROJECT_ID

# Grant service account access to the secret
gcloud secrets add-iam-policy-binding ingest-api-key \
    --member="serviceAccount:nvidia-blog-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID

# Update Cloud Run service to use the secret
gcloud run services update nvidia-blog-agent \
    --update-secrets INGEST_API_KEY=ingest-api-key:latest \
    --region us-central1 \
    --project $PROJECT_ID
```

Then clients calling `/ingest` must include the header:
```
X-API-Key: your-secret-api-key-here
```

## Step 5: Verify Deployment

### Test the Health Endpoint

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe nvidia-blog-agent \
    --region us-central1 \
    --format 'value(status.url)' \
    --project $PROJECT_ID)

# Test health endpoint
curl $SERVICE_URL/health
```

### Test the /ask Endpoint

```bash
# Test QA endpoint
curl -X POST $SERVICE_URL/ask \
    -H "Content-Type: application/json" \
    -d '{
        "question": "What did NVIDIA say about RAG on GPUs?",
        "top_k": 5
    }'
```

### Test the /ingest Endpoint

```bash
# Test ingestion endpoint (if API key is set, include it)
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
| `VERTEX_LOCATION` | Vertex AI region | `us-central1` |
| `RAG_DOCS_BUCKET` | GCS bucket for documents | `gs://nvidia-blog-rag-docs` |
| `STATE_PATH` | State persistence path | `gs://nvidia-blog-agent-state/state.json` |
| `GEMINI_MODEL_NAME` | Gemini model name | `gemini-1.5-pro` |
| `GEMINI_LOCATION` | Gemini region | `us-central1` |

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
4. Check that Vertex AI RAG corpus exists and is accessible

### Authentication Errors

1. Verify service account has correct IAM roles
2. Check that Application Default Credentials are working (automatic in Cloud Run)
3. Verify project ID is correct

### RAG Retrieval Fails

1. Verify `RAG_CORPUS_ID` is correct
2. Check that corpus is in the same region as `VERTEX_LOCATION`
3. Verify documents are ingested in the GCS bucket
4. Check Vertex AI Search data store is synced

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
  --set-env-vars "VERTEX_LOCATION=us-central1" \
  --set-env-vars "RAG_DOCS_BUCKET=gs://nvidia-blog-rag-docs" \
  --set-env-vars "STATE_PATH=gs://nvidia-blog-agent-state/state.json" \
  --set-env-vars "GEMINI_MODEL_NAME=gemini-1.5-pro" \
  --set-env-vars "GEMINI_LOCATION=us-central1" \
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

## References

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Run Best Practices](https://cloud.google.com/run/docs/tips)
- [Vertex AI RAG Setup](VERTEX_RAG_SETUP.md)
- [Engineering Status Report](ENGINEERING_STATUS_REPORT.md)

