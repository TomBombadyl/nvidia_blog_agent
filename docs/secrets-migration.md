# Secrets Migration Guide

## Overview

This guide explains how to migrate from hardcoded secrets to Google Cloud Secret Manager for better security and management.

## Current Status

✅ **Already using Secret Manager:**
- `INGEST_API_KEY` → Secret Manager: `ingest-api-key`

❌ **Needs Migration:**
- `RAG_CORPUS_ID` → Should use Secret Manager: `rag-corpus-id`

## Changes Made

### 1. Code Changes (`nvidia_blog_agent/config.py`)

The configuration now tries Secret Manager first, then falls back to environment variables:

```python
# Try Secret Manager first
rag_uuid = get_secret("rag-corpus-id", project_id=project_id)
if not rag_uuid:
    # Fallback to environment variable (for local dev)
    rag_uuid = os.environ.get("RAG_CORPUS_ID") or os.environ.get("RAG_UUID")
```

### 2. Deployment Changes (`.github/workflows/deploy.yml`)

Updated to use `--set-secrets` instead of `--set-env-vars` for secrets:

```yaml
--set-env-vars "GOOGLE_CLOUD_PROJECT=...,USE_VERTEX_RAG=true,..." \
--set-secrets "INGEST_API_KEY=ingest-api-key:latest,RAG_CORPUS_ID=rag-corpus-id:latest"
```

## Steps to Complete Migration

### Step 1: Create Secret in Secret Manager

```bash
# Create the secret
echo -n "6917529027641081856" | gcloud secrets create rag-corpus-id \
  --project=nvidia-blog-agent \
  --data-file=-

# Grant Cloud Run service account access
gcloud secrets add-iam-policy-binding rag-corpus-id \
  --project=nvidia-blog-agent \
  --member="serviceAccount:nvidia-blog-agent-sa@nvidia-blog-agent.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Step 2: Update Cloud Run Service

**Option A: Via gcloud CLI**

```bash
gcloud run services update nvidia-blog-agent \
  --region=us-central1 \
  --project=nvidia-blog-agent \
  --remove-env-vars RAG_CORPUS_ID \
  --update-secrets RAG_CORPUS_ID=rag-corpus-id:latest
```

**Option B: Via Cloud Console**

1. Go to [Cloud Run Console](https://console.cloud.google.com/run?project=nvidia-blog-agent)
2. Click on `nvidia-blog-agent` service
3. Click "EDIT & DEPLOY NEW REVISION"
4. Go to "Variables & Secrets" tab
5. **Remove** `RAG_CORPUS_ID` from environment variables
6. Click "ADD SECRET" → Select `rag-corpus-id` → Environment variable name: `RAG_CORPUS_ID` → Version: `latest`
7. Click "DEPLOY"

### Step 3: Verify Deployment

```bash
# Check that secret is mounted (not in env vars)
gcloud run services describe nvidia-blog-agent \
  --region=us-central1 \
  --project=nvidia-blog-agent \
  --format="value(spec.template.spec.containers[0].env)"

# Should NOT show RAG_CORPUS_ID in env vars
# Should show it in secrets (check via console or describe with --format=json)
```

### Step 4: Test the Service

```bash
# Test health endpoint
curl https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/health

# Test ingestion (should use secret from Secret Manager)
curl -X POST https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{}'
```

## Local Development

For local development, you can still use environment variables:

```bash
# .env file or export
export RAG_CORPUS_ID=6917529027641081856
```

The code will automatically fall back to the environment variable if Secret Manager is not available or the secret doesn't exist.

## Benefits

1. **Security**: Secrets are encrypted and managed centrally
2. **Audit Trail**: Secret Manager provides access logs
3. **Versioning**: Secrets can be versioned and rolled back
4. **Rotation**: Easy to rotate secrets without code changes
5. **No Hardcoding**: Secrets never appear in environment variables or logs

## Troubleshooting

### Secret Not Found

If you see errors about `rag-corpus-id` not found:

1. Verify secret exists: `gcloud secrets list --project=nvidia-blog-agent`
2. Check IAM permissions: Service account needs `roles/secretmanager.secretAccessor`
3. Verify secret name matches: Should be `rag-corpus-id` (with hyphens)

### Fallback to Environment Variable

If Secret Manager fails, the code automatically falls back to `RAG_CORPUS_ID` environment variable. Check logs for warnings:

```
WARNING: Failed to retrieve secret rag-corpus-id from Secret Manager: ...
WARNING: Falling back to environment variable RAG_CORPUS_ID
```

## Migration Checklist

- [ ] Create `rag-corpus-id` secret in Secret Manager
- [ ] Grant service account access to the secret
- [ ] Update Cloud Run service to use secret reference
- [ ] Remove `RAG_CORPUS_ID` from environment variables
- [ ] Test service health endpoint
- [ ] Test ingestion endpoint
- [ ] Verify scheduler jobs work correctly
- [ ] Update documentation (if needed)

