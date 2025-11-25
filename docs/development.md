# Development Guide

Fast path to get the NVIDIA Blog Agent running locally and deployed.

## Local Development

### 1. Install Dependencies

```bash
pip install -e .
pip install "fastapi>=0.104.0" "uvicorn[standard]>=0.24.0"
```

### 2. Configure Environment

Create `.env` file:
```bash
USE_VERTEX_RAG=true
RAG_CORPUS_ID=your_corpus_id
VERTEX_LOCATION=us-east5
RAG_DOCS_BUCKET=gs://nvidia-blog-rag-docs
GEMINI_MODEL_NAME=gemini-2.0-flash-001
GEMINI_LOCATION=us-east5
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

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

## Testing

### Run All Tests

```bash
pytest -v
```

### Test Categories

- **Unit tests**: `pytest tests/unit/`
- **Workflow tests**: `pytest tests/workflows/`
- **E2E tests**: `pytest tests/e2e/`

### Local Service Testing

The `scripts/test_service_local.py` script provides automated smoke tests for all endpoints.

## Troubleshooting

### Service Won't Start

- Check environment variables are set correctly
- Verify Vertex AI RAG corpus ID is correct
- Ensure service account JSON is valid

### Empty Results from /ask

- Run ingestion first: `python scripts/run_ingest.py`
- Wait a few minutes for Vertex AI Search to index documents
- Verify RAG corpus ID matches your setup

### Import Errors

```bash
pip install google-cloud-storage google-cloud-aiplatform
```

## Next Steps

Once local testing passes:
1. Deploy to Cloud Run (see [deployment.md](deployment.md))
2. Set up Cloud Scheduler for daily ingestion
3. Configure monitoring and alerts

