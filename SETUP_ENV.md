# Environment Setup for First Ingestion Run

## Quick Setup Steps

### 1. Create .env file from template

```bash
cp env.template .env
```

### 2. Edit .env with your actual values

You need to fill in these **required** values:

```bash
# GCP Project
GOOGLE_CLOUD_PROJECT=nvidia-blog-agent

# Gemini Configuration
GEMINI_MODEL_NAME=gemini-1.5-pro
GEMINI_LOCATION=us-east5

# Vertex RAG Configuration
USE_VERTEX_RAG=true
RAG_CORPUS_ID=YOUR_ACTUAL_CORPUS_ID_HERE        # ⚠️ REPLACE THIS
VERTEX_LOCATION=us-east5
RAG_DOCS_BUCKET=gs://nvidia-blog-rag-docs

# State Persistence (use GCS for production)
STATE_PATH=gs://nvidia-blog-agent-state/state.json

# Service Account (local path to your JSON key file)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-service-account.json  # ⚠️ REPLACE THIS
```

### 3. Get your RAG Corpus ID

From the Vertex AI RAG Engine Console:
1. Go to [Vertex AI RAG Engine](https://console.cloud.google.com/ai/rag)
2. Click on your corpus
3. Copy the **numeric ID** from the resource name:
   - Format: `projects/nvidia-blog-agent/locations/us-east5/ragCorpora/{CORPUS_ID}`
   - Copy just the `{CORPUS_ID}` part (the numeric string)

### 4. Verify buckets exist

```bash
# Check docs bucket
gsutil ls gs://nvidia-blog-rag-docs

# Check state bucket
gsutil ls gs://nvidia-blog-agent-state
```

### 5. Run ingestion

```bash
python scripts/run_ingest.py \
  --state-path gs://nvidia-blog-agent-state/state.json \
  --verbose
```

### 6. Verify ingestion

```bash
# Check GCS docs bucket
gsutil ls gs://nvidia-blog-rag-docs | head -20

# Check state
gsutil cat gs://nvidia-blog-agent-state/state.json
```

### 7. Test QA

```bash
python scripts/run_qa.py "What did NVIDIA say about RAG on GPUs?" --top-k 8 --verbose
```

## Troubleshooting

### Missing RAG_CORPUS_ID
- Get it from Vertex AI RAG Engine Console
- It's the numeric ID in the corpus resource name

### Authentication errors
- Verify `GOOGLE_APPLICATION_CREDENTIALS` points to a valid service account JSON
- Ensure service account has `roles/aiplatform.user` and `roles/storage.objectAdmin`

### Bucket not found
- Create buckets if they don't exist:
  ```bash
  gsutil mb -p nvidia-blog-agent -l us-east5 gs://nvidia-blog-rag-docs
  gsutil mb -p nvidia-blog-agent -l us-east5 gs://nvidia-blog-agent-state
  ```

### Documents not appearing in Vertex AI Search
- Wait 2-5 minutes after ingestion for indexing
- Trigger manual reimport in Vertex AI Search Console if needed

