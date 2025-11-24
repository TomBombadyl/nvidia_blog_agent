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

Copy `env.template` to `.env` and set:
- `USE_VERTEX_RAG=true`
- `RAG_CORPUS_ID=your_corpus_id`
- `VERTEX_LOCATION=us-central1`
- `RAG_DOCS_BUCKET=gs://nvidia-blog-rag-docs`
- `GEMINI_MODEL_NAME=gemini-1.5-pro`
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

## Cloud Run Deployment (15 minutes)

### 1. Build Container

```bash
export PROJECT_ID="nvidia-blog-agent"
gcloud builds submit --tag gcr.io/$PROJECT_ID/nvidia-blog-agent:latest
```

### 2. Create Service Account

```bash
gcloud iam service-accounts create nvidia-blog-agent-sa \
    --display-name="NVIDIA Blog Agent Cloud Run Service Account"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:nvidia-blog-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:nvidia-blog-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"
```

### 3. Deploy to Cloud Run

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
    --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
    --set-env-vars "USE_VERTEX_RAG=true" \
    --set-env-vars "RAG_CORPUS_ID=YOUR_CORPUS_ID" \
    --set-env-vars "VERTEX_LOCATION=us-central1" \
    --set-env-vars "RAG_DOCS_BUCKET=gs://nvidia-blog-rag-docs" \
    --set-env-vars "STATE_PATH=gs://nvidia-blog-agent-state/state.json" \
    --set-env-vars "GEMINI_MODEL_NAME=gemini-1.5-pro" \
    --set-env-vars "GEMINI_LOCATION=us-central1"
```

### 4. Test Deployed Service

```bash
SERVICE_URL=$(gcloud run services describe nvidia-blog-agent \
    --region us-central1 --format='value(status.url)')

curl "$SERVICE_URL/health"
curl -X POST "$SERVICE_URL/ask" \
    -H "Content-Type: application/json" \
    -d '{"question": "What did NVIDIA say about RAG?", "top_k": 8}'
```

## Kaggle Notebook Integration

Copy `scripts/kaggle_notebook_example.py` into a Kaggle notebook and update `SERVICE_URL`:

```python
import requests

SERVICE_URL = "https://nvidia-blog-agent-xxxxx-uc.a.run.app"

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

## Next Steps

1. ✅ Local testing passes
2. ✅ Cloud Run deployment successful
3. ✅ Service responds to queries
4. 🎯 Create Kaggle notebook for capstone demo
5. 🎯 Set up monitoring and alerts
6. 🎯 Add rate limiting if needed
