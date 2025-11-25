# PowerShell script to set up Cloud Scheduler for daily ingestion
# 
# NOTE: Cloud Scheduler is already configured and running in production.
# This script is useful for:
# - Initial setup in new projects/environments
# - Reconfiguring the schedule or endpoint
# - Recovery if the scheduler job is deleted
#
# Current production status: ENABLED (runs daily at 7:00 AM ET)
# Job name: nvidia-blog-daily-ingest

$PROJECT_ID = "nvidia-blog-agent"
$REGION = "us-central1"
$SERVICE_NAME = "nvidia-blog-agent"
$SCHEDULER_JOB_NAME = "nvidia-blog-daily-ingest"

Write-Host "=== Setting Up Cloud Scheduler for Daily Ingestion ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Get API Key (from environment or generate)
Write-Host "Step 1: Getting INGEST_API_KEY..." -ForegroundColor Yellow
$INGEST_KEY = $env:INGEST_API_KEY
if (-not $INGEST_KEY) {
    Write-Host "INGEST_API_KEY not set in environment. Generating new one..." -ForegroundColor Yellow
    $INGEST_KEY = python -c "import secrets; print(secrets.token_urlsafe(32))"
    Write-Host "Generated API Key: $INGEST_KEY" -ForegroundColor Green
    Write-Host "⚠️  SAVE THIS KEY - You'll need it for Cloud Scheduler" -ForegroundColor Red
} else {
    Write-Host "Using INGEST_API_KEY from environment" -ForegroundColor Green
}
Write-Host ""

# Step 2: Get Service URL (from environment or gcloud)
Write-Host "Step 2: Getting Cloud Run service URL..." -ForegroundColor Yellow
$SERVICE_URL = $env:SERVICE_URL
if (-not $SERVICE_URL) {
    Write-Host "SERVICE_URL not set in environment. Looking up from Cloud Run..." -ForegroundColor Yellow
    try {
        $SERVICE_URL = gcloud run services describe $SERVICE_NAME `
            --region $REGION `
            --format='value(status.url)' `
            --project $PROJECT_ID 2>&1
        
        if ($LASTEXITCODE -eq 0 -and $SERVICE_URL) {
            Write-Host "✅ Service found: $SERVICE_URL" -ForegroundColor Green
        } else {
            Write-Host "❌ Service not found or Cloud Run API not enabled" -ForegroundColor Red
            Write-Host ""
            Write-Host "You need to:" -ForegroundColor Yellow
            Write-Host "1. Enable Cloud Run API: https://console.cloud.google.com/apis/api/run.googleapis.com/overview?project=$PROJECT_ID" -ForegroundColor White
            Write-Host "2. Deploy the service first (see CLOUD_RUN_DEPLOYMENT.md)" -ForegroundColor White
            Write-Host "   Or set SERVICE_URL environment variable manually" -ForegroundColor White
            exit 1
        }
    } catch {
        Write-Host "❌ Error checking service: $_" -ForegroundColor Red
        Write-Host "You can set SERVICE_URL environment variable manually" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "✅ Using SERVICE_URL from environment: $SERVICE_URL" -ForegroundColor Green
}
Write-Host ""

# Step 3: Enable Cloud Scheduler API
Write-Host "Step 3: Enabling Cloud Scheduler API..." -ForegroundColor Yellow
gcloud services enable cloudscheduler.googleapis.com --project=$PROJECT_ID
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Cloud Scheduler API enabled" -ForegroundColor Green
} else {
    Write-Host "⚠️  Cloud Scheduler API may already be enabled or you need permissions" -ForegroundColor Yellow
}
Write-Host ""

# Step 4: Update Cloud Run service with API key (if not already set)
Write-Host "Step 4: Updating Cloud Run service with INGEST_API_KEY..." -ForegroundColor Yellow
Write-Host "Do you want to update the Cloud Run service with the API key? (y/N)" -ForegroundColor Cyan
$update = Read-Host
if ($update -eq "y" -or $update -eq "Y") {
    gcloud run services update $SERVICE_NAME `
        --region $REGION `
        --update-env-vars "INGEST_API_KEY=$INGEST_KEY" `
        --project $PROJECT_ID
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Cloud Run service updated with INGEST_API_KEY" -ForegroundColor Green
    } else {
        Write-Host "❌ Failed to update service" -ForegroundColor Red
    }
} else {
    Write-Host "⏭️  Skipping service update. Make sure to set INGEST_API_KEY manually." -ForegroundColor Yellow
}
Write-Host ""

# Step 5: Create Cloud Scheduler job
Write-Host "Step 5: Creating Cloud Scheduler job..." -ForegroundColor Yellow

# Check if job already exists
$existing = gcloud scheduler jobs describe $SCHEDULER_JOB_NAME `
    --location $REGION `
    --project $PROJECT_ID 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "⚠️  Job already exists. Updating..." -ForegroundColor Yellow
    gcloud scheduler jobs update http $SCHEDULER_JOB_NAME `
        --project=$PROJECT_ID `
        --location=$REGION `
        --schedule="0 7 * * *" `
        --time-zone="America/New_York" `
        --uri="$SERVICE_URL/ingest" `
        --http-method=POST `
        --headers="Content-Type=application/json,X-API-Key=$INGEST_KEY" `
        --message-body="{}" `
        --description="Daily ingestion of NVIDIA blog posts at 7:00 AM ET"
} else {
    Write-Host "Creating new scheduler job..." -ForegroundColor Yellow
    gcloud scheduler jobs create http $SCHEDULER_JOB_NAME `
        --project=$PROJECT_ID `
        --location=$REGION `
        --schedule="0 7 * * *" `
        --time-zone="America/New_York" `
        --uri="$SERVICE_URL/ingest" `
        --http-method=POST `
        --headers="Content-Type=application/json,X-API-Key=$INGEST_KEY" `
        --message-body="{}" `
        --description="Daily ingestion of NVIDIA blog posts at 7:00 AM ET"
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Cloud Scheduler job created/updated successfully!" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to create/update scheduler job" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Step 6: Verify the job
Write-Host "Step 6: Verifying scheduler job..." -ForegroundColor Yellow
gcloud scheduler jobs describe $SCHEDULER_JOB_NAME `
    --location=$REGION `
    --project=$PROJECT_ID `
    --format="yaml(schedule,timeZone,scheduleTime,httpTarget.uri)"

Write-Host ""
Write-Host "=== Setup Complete! ===" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Summary:" -ForegroundColor Cyan
Write-Host "  - Service URL: $SERVICE_URL" -ForegroundColor White
Write-Host "  - API Key: $INGEST_KEY" -ForegroundColor White
Write-Host "  - Schedule: 0 7 * * * (7:00 AM ET daily)" -ForegroundColor White
Write-Host "  - Job Name: $SCHEDULER_JOB_NAME" -ForegroundColor White
Write-Host ""
Write-Host "🧪 Test the job manually:" -ForegroundColor Cyan
Write-Host "  gcloud scheduler jobs run $SCHEDULER_JOB_NAME --location=$REGION --project=$PROJECT_ID" -ForegroundColor White
Write-Host ""
Write-Host "📊 View logs:" -ForegroundColor Cyan
Write-Host "  gcloud logging read `"resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME`" --limit 50 --project=$PROJECT_ID" -ForegroundColor White

