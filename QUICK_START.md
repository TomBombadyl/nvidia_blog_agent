# Quick Start Guide

This guide provides a fast path to get the NVIDIA Blog Agent running locally and deployed to Cloud Run.

## Three-Layer Architecture

1. **Core Library** (`nvidia_blog_agent/`): The engine (182 tests passing)
2. **CLI Scripts** (`scripts/run_ingest.py`, `scripts/run_qa.py`): Dev/ops tools
3. **Cloud Run API** (`service/app.py`): Public-facing HTTP service

**Technical Configuration**: This system uses Vertex AI RAG Engine with `text-embedding-005` embeddings, 1024-token chunks with 256-token overlap, and hybrid search enabled. See [CLOUD_RUN_DEPLOYMENT.md](CLOUD_RUN_DEPLOYMENT.md) for complete setup instructions.

## Local Development (5 minutes)

### 1. Install Dependencies

```bash
pip install -e .
pip install "fastapi>=0.104.0" "uvicorn[standard]>=0.24.0"
```

### 2. Configure Environment

Create a `.env` file and set:
- `USE_VERTEX_RAG=true`
- `RAG_CORPUS_ID=your_corpus_id`
- `VERTEX_LOCATION=us-east5`
- `RAG_DOCS_BUCKET=gs://nvidia-blog-rag-docs`
- `GEMINI_MODEL_NAME=gemini-2.0-flash-001`
- `GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json`

### 3. Test CLI Scripts

```bash
# Run ingestion
python scripts/run_ingest.py --verbose

# Ask a question
python scripts/run_qa.py "What did NVIDIA say about RAG on GPUs?" --top-k 8
```

### 4. Test HTTP Service Locally

```bash
# Terminal 1: Start service
uvicorn service.app:app --reload --port 8080

# Terminal 2: Run smoke tests
python scripts/test_service_local.py

# Or test manually
curl http://localhost:8080/health
curl -X POST http://localhost:8080/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What did NVIDIA say about RAG?", "top_k": 8}'
```

## Cloud Run Deployment (Automated)

### Quick Deploy

The easiest way to deploy is using the automated PowerShell script:

```powershell
# Set your RAG corpus ID
$env:RAG_CORPUS_ID = "YOUR_CORPUS_ID"

# Run the deployment script
.\deploy_cloud_run.ps1
```

The script automatically:
- ✅ Creates Artifact Registry repository if needed
- ✅ Configures all required IAM permissions
- ✅ Builds and pushes the Docker image
- ✅ Deploys to Cloud Run
- ✅ Sets up environment variables

### Manual Deployment

If you prefer manual deployment, see [CLOUD_RUN_DEPLOYMENT.md](CLOUD_RUN_DEPLOYMENT.md) for detailed instructions.

### Test Deployed Service

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe nvidia-blog-agent \
    --region us-central1 --format='value(status.url)')

# Test health endpoint (may require authentication depending on org policy)
curl "$SERVICE_URL/health"

# Test QA endpoint
curl -X POST "$SERVICE_URL/ask" \
    -H "Content-Type: application/json" \
    -d '{"question": "What did NVIDIA say about RAG?", "top_k": 8}'
```

**Note**: If you get `403 Forbidden`, your organization policy may require authentication. The service is still deployed and working - you'll need to authenticate requests.

## Kaggle Notebook Integration

Copy `scripts/kaggle_notebook_example.py` into a Kaggle notebook and update `SERVICE_URL`:

```python
import requests

# Update with your actual service URL (get it from deployment output or gcloud)
SERVICE_URL = "https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app"

def ask(question, top_k=8):
    resp = requests.post(
        f"{SERVICE_URL}/ask",
        json={"question": question, "top_k": top_k},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()

result = ask("What did NVIDIA say about RAG on GPUs?")
print(result["answer"])
```

**Note**: The service URL above is from the current deployment. Get your actual URL from:
- Deployment script output
- `gcloud run services describe nvidia-blog-agent --region us-central1 --format='value(status.url)'`

## Documentation

- **[LOCAL_TESTING.md](LOCAL_TESTING.md)**: Detailed local testing guide
- **[CLOUD_RUN_DEPLOYMENT.md](CLOUD_RUN_DEPLOYMENT.md)**: Complete setup and deployment guide
- **[ENGINEERING_STATUS_REPORT.md](ENGINEERING_STATUS_REPORT.md)**: Technical architecture details

## Troubleshooting

### Service won't start locally
- Check environment variables are set correctly
- Verify Vertex AI RAG corpus ID is correct
- Ensure service account JSON is valid

### Cloud Run deployment fails
- Verify service account has correct IAM roles
- Check that all environment variables are set
- Review Cloud Run logs: `gcloud logging read ...`

### Empty results from /ask
- Run ingestion first: `python scripts/run_ingest.py`
- Wait a few minutes for Vertex AI Search to index documents
- Verify RAG corpus ID matches your setup

## Current Deployment Status

**✅ PRODUCTION DEPLOYMENT ACTIVE**

- **Service URL**: `https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app`
- **Status**: Ready and serving traffic
- **Cloud Scheduler**: Enabled (daily at 7:00 AM ET)
- **RAG Corpus**: Active with 100+ blog posts indexed

**To get your service URL**:
```bash
gcloud run services describe nvidia-blog-agent \
    --region us-central1 \
    --format='value(status.url)' \
    --project nvidia-blog-agent
```

**To get your INGEST_API_KEY**: Check the deployment script output or Cloud Run service environment variables.

**For complete project status**: See [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)

## Next Steps

1. ✅ Local testing passes
2. ✅ Cloud Run deployment successful
3. ✅ Service responds to queries
4. 🎯 Set up Cloud Scheduler for daily ingestion: `.\setup_scheduler.ps1`
5. 🎯 Create Kaggle notebook for capstone demo
6. 🎯 Set up monitoring and alerts
7. 🎯 Add rate limiting if needed
