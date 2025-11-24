# Complete Setup Walkthrough - Step by Step

This guide will walk you through setting up the NVIDIA Blog Agent from scratch.

## Prerequisites Checklist

Before we start, make sure you have:
- [ ] Google Cloud Project: `nvidia-blog-agent`
- [ ] Service Account: `nvidia-blog-agent-sa@nvidia-blog-agent.iam.gserviceaccount.com`
- [ ] Vertex AI RAG Corpus ID: `6917529027641081856`
- [ ] GCS Bucket: `gs://nvidia-blog-rag-docs`
- [ ] Python 3.10+ installed
- [ ] `gcloud` CLI installed and authenticated

---

## Step 1: Set Up Application Default Credentials (ADC) - Project-Specific

Since your organization blocks service account key creation, we'll use Application Default Credentials.
**Important:** We'll do this WITHOUT changing any global gcloud defaults.

### 1.1 Authenticate with gcloud (Project-Specific)

```bash
# This will open a browser for you to sign in
# It stores credentials locally but doesn't change your gcloud config
gcloud auth application-default login --project=nvidia-blog-agent
```

**What this does:**
- Authenticates your user account
- Stores credentials locally (doesn't affect other projects)
- Sets quota project to avoid warnings
- Allows the system to use your credentials automatically

**Note:** This doesn't change your global gcloud configuration, so it won't affect your other projects.

### 1.2 Verify Authentication (Project-Specific)

```bash
# Test GCS access (explicitly specify project)
gsutil -p nvidia-blog-agent ls gs://nvidia-blog-rag-docs

# Or set project just for this command
$env:GOOGLE_CLOUD_PROJECT="nvidia-blog-agent"; gsutil ls gs://nvidia-blog-rag-docs
```

**Expected result:** You should see your buckets and be able to list them.

### 1.3 Verify Your User Has Required Permissions

Make sure your Google account has these roles on the project:
- `roles/aiplatform.user` (for Vertex AI)
- `roles/storage.objectAdmin` (for GCS buckets)

If you don't have these, ask your admin to grant them.

---

## Step 2: Configure Environment Variables

### 2.1 Update Your .env File

Open your `.env` file and make sure it looks like this:

```bash
# =============================================================================
# GCP PROJECT CONFIGURATION
# =============================================================================
GOOGLE_CLOUD_PROJECT=nvidia-blog-agent

# ⚠️ IMPORTANT: Comment out or remove GOOGLE_APPLICATION_CREDENTIALS
# We're using Application Default Credentials instead
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account.json

# =============================================================================
# GEMINI / LLM CONFIGURATION
# =============================================================================
GEMINI_MODEL_NAME=gemini-2.0-flash-001
GEMINI_LOCATION=us-east5

# =============================================================================
# VERTEX AI RAG CONFIGURATION
# =============================================================================
USE_VERTEX_RAG=true
RAG_CORPUS_ID=6917529027641081856
VERTEX_LOCATION=us-east5
RAG_DOCS_BUCKET=gs://nvidia-blog-rag-docs

# =============================================================================
# STATE PERSISTENCE
# =============================================================================
STATE_PATH=state.json

# =============================================================================
# OPTIONAL: INGEST API KEY (for protecting /ingest endpoint)
# =============================================================================
# Generate a strong key: openssl rand -hex 32
# INGEST_API_KEY=your-strong-random-key-here
```

**Key changes:**
- ✅ `GOOGLE_APPLICATION_CREDENTIALS` is commented out (we use ADC)
- ✅ All other values are set correctly
- ✅ `INGEST_API_KEY` is optional (only needed if you want to protect `/ingest`)

### 2.2 Verify Configuration Loading

Test that your configuration loads correctly:

```bash
# Load .env and test config (all project-specific, no global changes)
python -c "from dotenv import load_dotenv; import os; load_dotenv(); from nvidia_blog_agent.config import load_config_from_env; config = load_config_from_env(); print('✅ Config loaded successfully'); print('RAG Backend:', 'Vertex AI' if config.rag.use_vertex_rag else 'HTTP'); print('Corpus ID:', config.rag.uuid); print('Bucket:', config.rag.docs_bucket); print('Project:', os.environ.get('GOOGLE_CLOUD_PROJECT'))"
```

**Expected result:** Should print your configuration without errors.

**Note:** All configuration comes from your `.env` file - no global gcloud defaults needed!

---

## Step 3: Test Local Setup

### 3.1 Test RSS Feed Parsing

First, let's verify RSS feed parsing works:

```bash
python scripts/test_rss_feed.py
```

**Expected result:** Should fetch and parse the RSS feed, showing 100 posts with content.

### 3.2 Test Configuration and Authentication

```bash
# Test that you can access GCS (uses project from .env, no global config)
python -c "from dotenv import load_dotenv; import os; load_dotenv(); from google.cloud import storage; client = storage.Client(project=os.environ.get('GOOGLE_CLOUD_PROJECT')); bucket = client.bucket('nvidia-blog-rag-docs'); print('✅ Can access bucket:', bucket.name)"
```

**Expected result:** Should print the bucket name without errors.

**Note:** This uses the project from your `.env` file, not any global gcloud config.

---

## Step 4: Run Your First Ingestion (Optional - Test Run)

### 4.1 Run Ingestion with Verbose Logging

```bash
python scripts/run_ingest.py --verbose
```

**What this does:**
1. Fetches RSS feed from `https://developer.nvidia.com/blog/feed/`
2. Discovers new posts
3. Extracts content from RSS feed (no 403 errors!)
4. Summarizes posts with Gemini 1.5 Pro
5. Writes documents to `gs://nvidia-blog-rag-docs/{blog_id}.txt`
6. Vertex AI Search automatically indexes them

**Expected result:** Should complete successfully and show:
- Number of posts discovered
- Number of new posts
- Number of summaries created

### 4.2 Verify Documents Were Written

```bash
# List documents in GCS bucket
gsutil ls gs://nvidia-blog-rag-docs | head -10

# Check a specific document
gsutil cat gs://nvidia-blog-rag-docs/$(gsutil ls gs://nvidia-blog-rag-docs | head -1)
```

**Expected result:** Should see `.txt` and `.metadata.json` files in the bucket.

---

## Step 5: Test QA (Query the System)

### 5.1 Wait for Indexing (Important!)

After ingestion, wait 2-5 minutes for Vertex AI Search to index the documents.

### 5.2 Run a Test Query

```bash
python scripts/run_qa.py "What did NVIDIA say about RAG on GPUs?" --top-k 8 --verbose
```

**Expected result:** Should return an answer with source documents.

---

## Step 6: Set Up API Key for Ingestion Protection (Optional)

If you want to protect the `/ingest` endpoint when deployed:

### 6.1 Generate a Strong API Key

```bash
# On Linux/Mac
INGEST_KEY=$(openssl rand -hex 32)
echo $INGEST_KEY

# On Windows PowerShell
$INGEST_KEY = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 64 | ForEach-Object {[char]$_})
Write-Host $INGEST_KEY
```

**Save this key securely!** You'll need it to call `/ingest`.

### 6.2 Add to .env (for local testing)

```bash
# Add to your .env file
INGEST_API_KEY=your-generated-key-here
```

### 6.3 Test Protected Endpoint Locally

```bash
# Start the service locally
uvicorn service.app:app --reload --port 8080

# In another terminal, test without key (should fail)
curl -X POST http://localhost:8080/ingest -H "Content-Type: application/json" -d '{}'

# Test with key (should work)
curl -X POST http://localhost:8080/ingest \
    -H "Content-Type: application/json" \
    -H "X-API-Key: your-generated-key-here" \
    -d '{}'
```

---

## Step 7: Deploy to Cloud Run (Production)

### 7.1 Create Secret in Secret Manager

```bash
# Create the secret
echo -n "your-generated-key-here" | gcloud secrets create ingest-api-key \
    --data-file=- \
    --project=nvidia-blog-agent

# Grant service account access
gcloud secrets add-iam-policy-binding ingest-api-key \
    --member="serviceAccount:nvidia-blog-agent-sa@nvidia-blog-agent.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --project=nvidia-blog-agent
```

### 7.2 Build and Deploy

```bash
# Set project
export PROJECT_ID="nvidia-blog-agent"

# Build container
gcloud builds submit --tag gcr.io/$PROJECT_ID/nvidia-blog-agent:latest

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
    --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
    --set-env-vars "USE_VERTEX_RAG=true" \
    --set-env-vars "RAG_CORPUS_ID=6917529027641081856" \
    --set-env-vars "VERTEX_LOCATION=us-east5" \
    --set-env-vars "RAG_DOCS_BUCKET=gs://nvidia-blog-rag-docs" \
    --set-env-vars "STATE_PATH=gs://nvidia-blog-agent-state/state.json" \
    --set-env-vars "GEMINI_MODEL_NAME=gemini-2.0-flash-001" \
    --set-env-vars "GEMINI_LOCATION=us-east5" \
    --set-secrets "INGEST_API_KEY=ingest-api-key:latest"
```

### 7.3 Test Deployed Service

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe nvidia-blog-agent \
    --region us-central1 \
    --format='value(status.url)')

# Test public /ask endpoint
curl -X POST $SERVICE_URL/ask \
    -H "Content-Type: application/json" \
    -d '{"question": "What did NVIDIA say about RAG?", "top_k": 8}'

# Test protected /ingest endpoint
curl -X POST $SERVICE_URL/ingest \
    -H "Content-Type: application/json" \
    -H "X-API-Key: your-generated-key-here" \
    -d '{}'
```

---

## Troubleshooting

### Authentication Errors

**Problem:** `403 Forbidden` or `Permission denied`

**Solution:**
1. Verify ADC is set up: `gcloud auth application-default login --project=nvidia-blog-agent`
2. Check your user has required IAM roles on the `nvidia-blog-agent` project
3. Verify project ID in `.env` file: `GOOGLE_CLOUD_PROJECT=nvidia-blog-agent`
4. **Don't rely on global gcloud config** - everything should come from `.env`

### Configuration Errors

**Problem:** `KeyError: RAG_CORPUS_ID is required`

**Solution:**
1. Check `.env` file has all required variables
2. Verify `USE_VERTEX_RAG=true` (lowercase "true")
3. Run: `python -c "from nvidia_blog_agent.config import load_config_from_env; load_config_from_env()"`

### GCS Access Errors

**Problem:** `403 Forbidden` when accessing bucket

**Solution:**
1. Verify bucket exists: `gsutil ls gs://nvidia-blog-rag-docs`
2. Check your user has `roles/storage.objectAdmin` role
3. Verify bucket name is correct in `.env`

### Vertex AI Errors

**Problem:** `403 Forbidden` when accessing Vertex AI

**Solution:**
1. Check your user has `roles/aiplatform.user` role
2. Verify `VERTEX_LOCATION=us-east5` matches your corpus location
3. Verify `RAG_CORPUS_ID` is correct

---

## Quick Reference

### Local Development Commands

```bash
# Run ingestion
python scripts/run_ingest.py --verbose

# Ask a question
python scripts/run_qa.py "Your question here" --top-k 8

# Test RSS feed
python scripts/test_rss_feed.py

# Start local service
uvicorn service.app:app --reload --port 8080
```

### Production Commands

```bash
# Query public endpoint
curl -X POST $SERVICE_URL/ask \
    -H "Content-Type: application/json" \
    -d '{"question": "Your question", "top_k": 8}'

# Trigger ingestion (protected)
curl -X POST $SERVICE_URL/ingest \
    -H "Content-Type: application/json" \
    -H "X-API-Key: your-key" \
    -d '{}'
```

---

## Next Steps

1. ✅ Set up ADC (Step 1)
2. ✅ Configure .env (Step 2)
3. ✅ Test locally (Steps 3-5)
4. ✅ Deploy to Cloud Run (Step 7)
5. 🎉 Share your public `/ask` endpoint!

Your system is now ready with:
- ✅ Public `/ask` endpoint (anyone can query)
- ✅ Protected `/ingest` endpoint (only you can trigger)
- ✅ RSS feed support (no 403 errors)
- ✅ Vertex AI RAG backend (automatic indexing)

