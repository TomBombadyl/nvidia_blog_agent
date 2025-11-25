# PowerShell script to deploy Cloud Run service
# Run this after building the container image

$PROJECT_ID = "nvidia-blog-agent"
$SERVICE_NAME = "nvidia-blog-agent"
$REGION = "us-central1"
$ARTIFACT_REGISTRY_REPO = "nvidia-blog-agent"
$SERVICE_ACCOUNT = "nvidia-blog-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Get configuration from environment or set defaults
$RAG_CORPUS_ID = $env:RAG_CORPUS_ID
if (-not $RAG_CORPUS_ID) {
    Write-Host "[WARNING] RAG_CORPUS_ID not set. Please set it:" -ForegroundColor Yellow
    Write-Host "   `$env:RAG_CORPUS_ID = 'YOUR_CORPUS_ID'" -ForegroundColor White
    Write-Host ""
    $RAG_CORPUS_ID = Read-Host "Enter your RAG Corpus ID"
}

$INGEST_KEY = $env:INGEST_API_KEY
if (-not $INGEST_KEY) {
    Write-Host "[WARNING] INGEST_API_KEY not set. Generating one..." -ForegroundColor Yellow
    $INGEST_KEY = python -c "import secrets; print(secrets.token_urlsafe(32))"
    Write-Host "Generated API Key: $INGEST_KEY" -ForegroundColor Green
    Write-Host "[WARNING] SAVE THIS KEY - You'll need it for Cloud Scheduler!" -ForegroundColor Red
    Write-Host ""
}

Write-Host "=== Deploying Cloud Run Service ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Project: $PROJECT_ID" -ForegroundColor White
Write-Host "  Service: $SERVICE_NAME" -ForegroundColor White
Write-Host "  Region: $REGION" -ForegroundColor White
Write-Host "  Service Account: $SERVICE_ACCOUNT" -ForegroundColor White
Write-Host "  RAG Corpus ID: $RAG_CORPUS_ID" -ForegroundColor White
Write-Host ""

# Ensure Artifact Registry repository exists
Write-Host "Ensuring Artifact Registry repository exists..." -ForegroundColor Yellow
$repo_exists = gcloud artifacts repositories describe $ARTIFACT_REGISTRY_REPO `
    --location=$REGION `
    --project=$PROJECT_ID 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating Artifact Registry repository..." -ForegroundColor Yellow
    gcloud artifacts repositories create $ARTIFACT_REGISTRY_REPO `
        --repository-format=docker `
        --location=$REGION `
        --description="Container images for NVIDIA Blog Agent" `
        --project=$PROJECT_ID
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Artifact Registry repository created" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Failed to create Artifact Registry repository" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "[OK] Artifact Registry repository exists" -ForegroundColor Green
}
Write-Host ""

# Check if image exists
Write-Host "Checking if container image exists..." -ForegroundColor Yellow
$image = "${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REGISTRY_REPO}/${SERVICE_NAME}:latest"
$image_list = gcloud artifacts docker images list `
    --repository=$ARTIFACT_REGISTRY_REPO `
    --location=$REGION `
    --format="value(package)" `
    --filter="package:${SERVICE_NAME} AND tags:latest" `
    --project=$PROJECT_ID 2>&1

# Check if we got any results and command succeeded
$image_exists = ($LASTEXITCODE -eq 0 -and $image_list -ne "")

if (-not $image_exists) {
    Write-Host "[WARNING] Container image not found. Building..." -ForegroundColor Yellow
    
    # Ensure Cloud Build has necessary permissions
    Write-Host "Ensuring Cloud Build permissions are configured..." -ForegroundColor Yellow
    
    # Get project number for service account identification
    $PROJECT_NUMBER = gcloud projects describe $PROJECT_ID --format="value(projectNumber)" 2>&1
    if ($LASTEXITCODE -ne 0 -or -not $PROJECT_NUMBER) {
        Write-Host "[ERROR] Failed to get project number" -ForegroundColor Red
        exit 1
    }
    
    # Define service accounts
    $COMPUTE_SA = "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
    $CLOUD_BUILD_SA = "${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
    
    # Grant permissions to Compute Engine default service account (for source uploads and logs)
    Write-Host "Granting permissions to Compute Engine default service account..." -ForegroundColor Yellow
    
    # Storage permissions for source uploads
    gcloud projects add-iam-policy-binding $PROJECT_ID `
        --member="serviceAccount:${COMPUTE_SA}" `
        --role="roles/storage.objectAdmin" `
        --condition=None `
        --quiet 2>&1 | Out-Null
    
    # Logging permissions (for Cloud Build logs)
    gcloud projects add-iam-policy-binding $PROJECT_ID `
        --member="serviceAccount:${COMPUTE_SA}" `
        --role="roles/logging.logWriter" `
        --condition=None `
        --quiet 2>&1 | Out-Null
    
    # Grant permissions to Cloud Build service account
    Write-Host "Granting permissions to Cloud Build service account..." -ForegroundColor Yellow
        
        # Storage permissions for source uploads
        gcloud projects add-iam-policy-binding $PROJECT_ID `
            --member="serviceAccount:${CLOUD_BUILD_SA}" `
            --role="roles/storage.objectAdmin" `
            --condition=None `
            --quiet 2>&1 | Out-Null
        
        # Artifact Registry permissions at project level (required for pushing images)
        Write-Host "Granting project-level Artifact Registry permissions..." -ForegroundColor Yellow
        gcloud projects add-iam-policy-binding $PROJECT_ID `
            --member="serviceAccount:${CLOUD_BUILD_SA}" `
            --role="roles/artifactregistry.writer" `
            --condition=None `
            --quiet 2>&1 | Out-Null
        
        # Artifact Registry permissions at repository level (more specific)
        Write-Host "Granting repository-level Artifact Registry permissions..." -ForegroundColor Yellow
        # Grant to Cloud Build service account
        gcloud artifacts repositories add-iam-policy-binding $ARTIFACT_REGISTRY_REPO `
            --location=$REGION `
            --member="serviceAccount:${CLOUD_BUILD_SA}" `
            --role="roles/artifactregistry.writer" `
            --project=$PROJECT_ID `
            --quiet 2>&1 | Out-Null
        # Also grant to Compute Engine default service account (Docker builder may use this)
        gcloud artifacts repositories add-iam-policy-binding $ARTIFACT_REGISTRY_REPO `
            --location=$REGION `
            --member="serviceAccount:${COMPUTE_SA}" `
            --role="roles/artifactregistry.writer" `
            --project=$PROJECT_ID `
            --quiet 2>&1 | Out-Null
        
    # Logging permissions (for Cloud Build logs)
    gcloud projects add-iam-policy-binding $PROJECT_ID `
        --member="serviceAccount:${CLOUD_BUILD_SA}" `
        --role="roles/logging.logWriter" `
        --condition=None `
        --quiet 2>&1 | Out-Null
    
    Write-Host "[OK] Permissions configured. Waiting 10 seconds for IAM propagation..." -ForegroundColor Green
    Start-Sleep -Seconds 10
    
    Write-Host "Building and pushing image: $image" -ForegroundColor Cyan
    
    # Create temporary cloudbuild.yaml for explicit build control
    $cloudbuildYaml = @"
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-t', '$image', '.']
- name: 'gcr.io/cloud-builders/docker'
  args: ['push', '$image']
images:
- '$image'
options:
  logging: CLOUD_LOGGING_ONLY
"@
    
    $tempYaml = [System.IO.Path]::GetTempFileName() + ".yaml"
    $cloudbuildYaml | Out-File -FilePath $tempYaml -Encoding utf8 -NoNewline
    
    $maxRetries = 3
    $retryCount = 0
    $buildSuccess = $false
    
    while ($retryCount -lt $maxRetries -and -not $buildSuccess) {
        if ($retryCount -gt 0) {
            Write-Host "Retry attempt $retryCount of $maxRetries..." -ForegroundColor Yellow
            Write-Host "Re-granting permissions before retry..." -ForegroundColor Yellow
            # Re-grant permissions in case they didn't propagate
            gcloud artifacts repositories add-iam-policy-binding $ARTIFACT_REGISTRY_REPO `
                --location=$REGION `
                --member="serviceAccount:${CLOUD_BUILD_SA}" `
                --role="roles/artifactregistry.writer" `
                --project=$PROJECT_ID `
                --quiet 2>&1 | Out-Null
            gcloud artifacts repositories add-iam-policy-binding $ARTIFACT_REGISTRY_REPO `
                --location=$REGION `
                --member="serviceAccount:${COMPUTE_SA}" `
                --role="roles/artifactregistry.writer" `
                --project=$PROJECT_ID `
                --quiet 2>&1 | Out-Null
            Start-Sleep -Seconds 30
        }
        
        gcloud builds submit --config=$tempYaml --project=$PROJECT_ID
        
        if ($LASTEXITCODE -eq 0) {
            $buildSuccess = $true
            Write-Host "[OK] Image built and pushed" -ForegroundColor Green
        } else {
            $retryCount++
            if ($retryCount -lt $maxRetries) {
                Write-Host "[WARNING] Build failed, will retry after waiting..." -ForegroundColor Yellow
            } else {
                Write-Host "[ERROR] Failed to build image after $maxRetries attempts" -ForegroundColor Red
                Write-Host "Check the error above. Common issues:" -ForegroundColor Yellow
                Write-Host "  - API propagation delay (wait a few minutes and retry)" -ForegroundColor White
                Write-Host "  - Missing service account permissions" -ForegroundColor White
                Write-Host "  - Cloud Build API not fully enabled" -ForegroundColor White
                Write-Host "" -ForegroundColor White
                Write-Host "Troubleshooting steps:" -ForegroundColor Yellow
                Write-Host "  1. Verify Cloud Build service account has permissions:" -ForegroundColor White
                Write-Host "     gcloud artifacts repositories get-iam-policy $ARTIFACT_REGISTRY_REPO --location=$REGION --project=$PROJECT_ID" -ForegroundColor Gray
                Write-Host "  2. Manually grant permissions if needed:" -ForegroundColor White
                Write-Host "     gcloud artifacts repositories add-iam-policy-binding $ARTIFACT_REGISTRY_REPO --location=$REGION --member=serviceAccount:${CLOUD_BUILD_SA} --role=roles/artifactregistry.writer --project=$PROJECT_ID" -ForegroundColor Gray
                Write-Host "  3. Wait 2-3 minutes for IAM propagation, then retry" -ForegroundColor White
                Remove-Item $tempYaml -ErrorAction SilentlyContinue
                exit 1
            }
        }
    }
    
    # Clean up temporary file
    Remove-Item $tempYaml -ErrorAction SilentlyContinue
} else {
    Write-Host "[OK] Image exists: $image" -ForegroundColor Green
}
Write-Host ""

# Deploy service
Write-Host "Deploying Cloud Run service..." -ForegroundColor Yellow
gcloud run deploy $SERVICE_NAME `
    --image $image `
    --platform managed `
    --region $REGION `
    --service-account $SERVICE_ACCOUNT `
    --allow-unauthenticated `
    --memory 2Gi `
    --cpu 2 `
    --timeout 300 `
    --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID" `
    --set-env-vars "USE_VERTEX_RAG=true" `
    --set-env-vars "RAG_CORPUS_ID=$RAG_CORPUS_ID" `
    --set-env-vars "VERTEX_LOCATION=us-east5" `
    --set-env-vars "RAG_DOCS_BUCKET=gs://nvidia-blog-rag-docs" `
    --set-env-vars "STATE_PATH=gs://nvidia-blog-agent-state/state.json" `
    --set-env-vars "GEMINI_MODEL_NAME=gemini-2.0-flash-001" `
    --set-env-vars "GEMINI_LOCATION=us-east5" `
    --set-env-vars "INGEST_API_KEY=$INGEST_KEY" `
    --project=$PROJECT_ID

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[OK] Deployment successful!" -ForegroundColor Green
    Write-Host ""
    
    # Get service URL
    $SERVICE_URL = gcloud run services describe $SERVICE_NAME `
        --region $REGION `
        --format='value(status.url)' `
        --project=$PROJECT_ID
    
    # Try to set IAM policy for public access (may fail due to org policy)
    Write-Host "Setting up public access..." -ForegroundColor Yellow
    gcloud run services add-iam-policy-binding $SERVICE_NAME `
        --region=$REGION `
        --member="allUsers" `
        --role="roles/run.invoker" `
        --project=$PROJECT_ID `
        --quiet 2>&1 | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Public access configured" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] Public access may be restricted by organization policy" -ForegroundColor Yellow
        Write-Host "  Service is deployed but may require authentication" -ForegroundColor White
    }
    Write-Host ""
    
    Write-Host "=== Deployment Summary ===" -ForegroundColor Cyan
    Write-Host "  Service URL: $SERVICE_URL" -ForegroundColor White
    Write-Host "  INGEST_API_KEY: $INGEST_KEY" -ForegroundColor White
    Write-Host ""
    Write-Host "Test the service:" -ForegroundColor Cyan
    Write-Host "  curl $SERVICE_URL/health" -ForegroundColor White
    Write-Host ""
    Write-Host "Next Steps:" -ForegroundColor Cyan
    Write-Host "  1. Save the INGEST_API_KEY above" -ForegroundColor White
    Write-Host "  2. Run setup_scheduler.ps1 to set up daily ingestion" -ForegroundColor White
    Write-Host "     Or use: `$env:INGEST_API_KEY='$INGEST_KEY'; `$env:SERVICE_URL='$SERVICE_URL'; .\setup_scheduler.ps1" -ForegroundColor White
} else {
    Write-Host "[ERROR] Deployment failed" -ForegroundColor Red
    exit 1
}

