# Local Testing Guide

This guide helps you test the FastAPI service locally before deploying to Cloud Run.

## Production Status

**Current Production Service**: `https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app`  
**Status**: ✅ Deployed and operational

For complete project status, see [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md).

## Prerequisites

1. **Install dependencies**:
   ```bash
   pip install -e .
   pip install "fastapi>=0.104.0" "uvicorn[standard]>=0.24.0"
   ```

2. **Set up environment variables**:
   - Create a `.env` file with your configuration values
   - Or set environment variables in your shell
   - See [SETUP_WALKTHROUGH.md](SETUP_WALKTHROUGH.md) for complete setup instructions
   - Required for Vertex AI RAG:
     - `GOOGLE_CLOUD_PROJECT`
     - `USE_VERTEX_RAG=true`
     - `RAG_CORPUS_ID`
     - `VERTEX_LOCATION`
     - `RAG_DOCS_BUCKET`
     - `GEMINI_MODEL_NAME`
     - `GEMINI_LOCATION`
     - `GOOGLE_APPLICATION_CREDENTIALS` (path to service account JSON for local dev)

**Note**: Technical configuration (embedding model, chunking, etc.) is set up in Vertex AI RAG Engine and Search. See [CLOUD_RUN_DEPLOYMENT.md](CLOUD_RUN_DEPLOYMENT.md) for setup instructions.

## Step 1: Start the Service

In one terminal, start the FastAPI service:

```bash
# From project root
uvicorn service.app:app --reload --port 8080
```

The `--reload` flag enables auto-reload on code changes (useful for development).

You should see output like:
```
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Initializing NVIDIA Blog Agent service...
INFO:     Using Gemini model: gemini-2.0-flash-001
INFO:     Using RAG backend: Vertex AI
INFO:     State path: state.json
INFO:     ✅ Service initialized successfully
INFO:     Application startup complete.
```

## Step 2: Run Smoke Tests

In another terminal, run the automated smoke test script:

```bash
# Run all tests
python scripts/test_service_local.py
```

Or test endpoints manually:

### Test Health Endpoint

```bash
curl http://localhost:8080/health
```

Expected response:
```json
{
  "status": "healthy",
  "qa_agent_ready": true,
  "rag_backend": "Vertex AI"
}
```

### Test Root Endpoint

```bash
curl http://localhost:8080/
```

Expected response:
```json
{
  "service": "NVIDIA Blog Agent API",
  "status": "healthy",
  "version": "0.1.0"
}
```

### Test /ask Endpoint

```bash
curl -X POST http://localhost:8080/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What did NVIDIA say about RAG on GPUs?",
    "top_k": 8
  }'
```

Expected response:
```json
{
  "answer": "Based on the NVIDIA blog posts...",
  "sources": [
    {
      "title": "Blog Post Title",
      "url": "https://developer.nvidia.com/blog/...",
      "score": 0.9234,
      "snippet": "Relevant snippet from the document..."
    }
  ]
}
```

### Test /ingest Endpoint

If you've set `INGEST_API_KEY` in your environment:

```bash
# With API key
curl -X POST http://localhost:8080/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{}'
```

Or if no API key is required (for local testing, you can temporarily disable it):

```bash
# Without API key (if not configured)
curl -X POST http://localhost:8080/ingest \
  -H "Content-Type: application/json" \
  -d '{}'
```

Expected response:
```json
{
  "discovered_count": 10,
  "new_count": 3,
  "ingested_count": 3,
  "message": "Successfully processed 3 new posts"
}
```

## Troubleshooting

### Service Won't Start

**Error**: `KeyError: "RAG_CORPUS_ID environment variable is required"`

**Solution**: Make sure all required environment variables are set. See [SETUP_WALKTHROUGH.md](SETUP_WALKTHROUGH.md) for the complete list.

**Error**: `ImportError: Vertex AI RAG dependencies are required`

**Solution**: Install dependencies:
```bash
pip install google-cloud-storage google-cloud-aiplatform
```

### Health Check Fails

**Error**: `503 Service Unavailable` or `"qa_agent_ready": false`

**Solution**: 
- Check that the service initialized successfully (look at startup logs)
- Verify your Vertex AI RAG corpus ID is correct
- Check that your service account has the right permissions

### /ask Returns Empty Results

**Possible causes**:
1. No documents in the RAG corpus yet (run ingestion first)
2. RAG corpus ID is incorrect
3. Documents haven't been indexed yet (wait a few minutes after ingestion)

**Solution**: Run ingestion first:
```bash
python scripts/run_ingest.py
```

### /ingest Fails with 401 Unauthorized

**Solution**: If you've configured `INGEST_API_KEY` in the service, you must include it in the request:
```bash
curl -X POST http://localhost:8080/ingest \
  -H "X-API-Key: your-api-key-here" \
  ...
```

For local testing, you can temporarily unset `INGEST_API_KEY` in your environment to disable the check.

## Next Steps

Once local testing passes:

1. ✅ All endpoints respond correctly
2. ✅ /ask returns answers with sources
3. ✅ /ingest processes new blog posts

You're ready to deploy to Cloud Run! 

### Quick Deploy

```powershell
# Set your RAG corpus ID
$env:RAG_CORPUS_ID = "YOUR_CORPUS_ID"

# Deploy using automated script
.\deploy_cloud_run.ps1
```

The deployment script handles everything automatically. See [CLOUD_RUN_DEPLOYMENT.md](CLOUD_RUN_DEPLOYMENT.md) for detailed instructions.
