# Setting Up Cloud Scheduler for Daily Ingestion

This guide will help you set up automated daily ingestion using Cloud Scheduler.

## ✅ Current Status

**Cloud Scheduler**: ✅ **CONFIGURED AND ENABLED**
- **Job Name**: `nvidia-blog-daily-ingest`
- **Schedule**: `0 7 * * *` (7:00 AM ET daily)
- **Status**: ENABLED
- **Endpoint**: `https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/ingest`

The scheduler is already set up and running. Use this guide if you need to modify the schedule or reconfigure it.

## Prerequisites

1. ✅ Cloud Run service deployed (use `.\deploy_cloud_run.ps1` to deploy)
2. ✅ INGEST_API_KEY generated and set in Cloud Run service (automatically handled by deployment script)
3. ✅ Cloud Scheduler API enabled

## Step 1: Generate INGEST_API_KEY

Generate a secure API key for protecting the `/ingest` endpoint:

```bash
# Generate a secure random key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Save this key securely** - you'll need it for:
- Cloud Run service environment variable
- Cloud Scheduler job headers

## Step 2: Deploy/Update Cloud Run Service with API Key

**Recommended**: Use the automated deployment script which handles API key generation automatically:

```powershell
# The deployment script automatically generates an INGEST_API_KEY if not provided
$env:RAG_CORPUS_ID = "YOUR_CORPUS_ID"
.\deploy_cloud_run.ps1
```

The script will:
- Generate an API key automatically if `INGEST_API_KEY` is not set
- Display the generated key (save it for Cloud Scheduler)
- Deploy the service with the API key configured

**Or manually update existing service**:
```bash
export INGEST_KEY="YOUR_GENERATED_KEY_HERE"  # From Step 1

gcloud run services update nvidia-blog-agent \
  --region us-central1 \
  --update-env-vars "INGEST_API_KEY=$INGEST_KEY" \
  --project nvidia-blog-agent
```

## Step 3: Get Your Cloud Run Service URL

```bash
export PROJECT_ID="nvidia-blog-agent"

SERVICE_URL=$(gcloud run services describe nvidia-blog-agent \
  --region us-central1 \
  --format='value(status.url)' \
  --project $PROJECT_ID)

echo "Service URL: $SERVICE_URL"
```

**Save this URL** - you'll need it for the scheduler job.

## Step 4: Enable Cloud Scheduler API

```bash
gcloud services enable cloudscheduler.googleapis.com --project=$PROJECT_ID
```

## Step 5: Create Cloud Scheduler Job

```bash
export PROJECT_ID="nvidia-blog-agent"
export SERVICE_URL="https://YOUR_SERVICE_URL_HERE"  # From Step 3
export INGEST_KEY="YOUR_GENERATED_KEY_HERE"  # From Step 1

gcloud scheduler jobs create http nvidia-blog-daily-ingest \
  --project=$PROJECT_ID \
  --location=us-central1 \
  --schedule="0 7 * * *" \
  --time-zone="America/New_York" \
  --uri="${SERVICE_URL}/ingest" \
  --http-method=POST \
  --headers="Content-Type=application/json,X-API-Key=${INGEST_KEY}" \
  --body="{}" \
  --description="Daily ingestion of NVIDIA blog posts at 7:00 AM ET"
```

## Step 6: Test the Scheduler Job

Test the job manually to make sure it works:

```bash
gcloud scheduler jobs run nvidia-blog-daily-ingest \
  --location=us-central1 \
  --project=$PROJECT_ID
```

Check the Cloud Run logs to verify ingestion ran successfully:

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=nvidia-blog-agent" \
  --limit 50 \
  --project=$PROJECT_ID \
  --format=json
```

## Verification

After setup, verify:

1. **Job exists**:
   ```bash
   gcloud scheduler jobs describe nvidia-blog-daily-ingest \
     --location=us-central1 \
     --project=$PROJECT_ID
   ```

2. **Job will run**:
   - Check the schedule: `0 7 * * *` (7:00 AM daily)
   - Time zone: `America/New_York` (US/Eastern)

3. **Next run time**:
   ```bash
   gcloud scheduler jobs describe nvidia-blog-daily-ingest \
     --location=us-central1 \
     --project=$PROJECT_ID \
     --format="value(scheduleTime)"
   ```

## Troubleshooting

### Job fails with 401/403
- Verify `INGEST_API_KEY` matches in both Cloud Run service and scheduler job
- Check that the API key is set correctly in Cloud Run environment variables

### Job fails with 404
- Verify the service URL is correct
- Ensure the `/ingest` endpoint exists and is accessible

### Job doesn't run
- Check Cloud Scheduler logs:
  ```bash
  gcloud logging read "resource.type=cloud_scheduler_job" \
    --limit 20 \
    --project=$PROJECT_ID
  ```
- Verify the schedule is correct (cron format: `0 7 * * *`)

## Quick Reference

**Update the job** (if you need to change schedule or URL):
```bash
gcloud scheduler jobs update http nvidia-blog-daily-ingest \
  --location=us-central1 \
  --schedule="0 7 * * *" \
  --uri="${SERVICE_URL}/ingest" \
  --headers="Content-Type=application/json,X-API-Key=${INGEST_KEY}"
```

**Delete the job** (if needed):
```bash
gcloud scheduler jobs delete nvidia-blog-daily-ingest \
  --location=us-central1 \
  --project=$PROJECT_ID
```

**List all scheduler jobs**:
```bash
gcloud scheduler jobs list --location=us-central1 --project=$PROJECT_ID
```

