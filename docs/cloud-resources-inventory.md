# Cloud Resources Inventory

**Project:** `nvidia-blog-agent`  
**Project Number:** `262844214274`  
**Last Updated:** 2025-11-25

## Overview

This document provides a comprehensive inventory of all cloud resources deployed for the NVIDIA Blog Agent system.

---

## 🚀 Cloud Run Service

### Service Details
- **Name:** `nvidia-blog-agent`
- **Region:** `us-central1`
- **URLs:**
  - Primary: `https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app`
  - Alternative: `https://nvidia-blog-agent-262844214274.us-central1.run.app`
- **Status:** ✅ Ready
- **Latest Revision:** `nvidia-blog-agent-00004-tmc`
- **Last Deployed:** 2025-11-25T00:39:29.144391Z
- **Deployed By:** dylant@synapgarden.com

### Configuration
- **Container Image:** `us-central1-docker.pkg.dev/nvidia-blog-agent/nvidia-blog-agent/nvidia-blog-agent:latest`
- **Container Port:** 8080
- **Service Account:** `nvidia-blog-agent-sa@nvidia-blog-agent.iam.gserviceaccount.com`
- **Resources:**
  - CPU: 2 cores
  - Memory: 2 GiB
- **Concurrency:** 160 requests per instance
- **Timeout:** 300 seconds
- **Max Scale:** 100 instances
- **Startup Probe:** TCP on port 8080, 240s timeout

### Environment Variables
- `GOOGLE_CLOUD_PROJECT=nvidia-blog-agent`
- `USE_VERTEX_RAG=true`
- `RAG_CORPUS_ID=6917529027641081856`
- `VERTEX_LOCATION=us-east5`
- `RAG_DOCS_BUCKET=gs://nvidia-blog-rag-docs`
- `STATE_PATH=gs://nvidia-blog-agent-state/state.json`
- `GEMINI_MODEL_NAME=gemini-2.0-flash-001`
- `GEMINI_LOCATION=us-east5`
- `INGEST_API_KEY=emik6JhmdDhsVCHxjfRqz1tgDEnxljPEWh2WTXwyPMw`

### API Endpoints
- `POST /ask` - Answer questions using RAG + Gemini
- `POST /ingest` - Trigger ingestion pipeline
- `POST /ask/batch` - Batch query endpoint
- `GET /analytics` - Usage analytics
- `GET /history` - Query history
- `GET /export` - Export functionality
- `GET /admin/stats` - Admin dashboard

---

## 📦 Cloud Storage Buckets

### 1. RAG Documents Bucket
- **Name:** `nvidia-blog-rag-docs`
- **Purpose:** Stores ingested blog post documents and metadata
- **Format:** 
  - `.txt` files for document content
  - `.metadata.json` files for document metadata
- **Location:** `us-central1`
- **Storage Class:** Standard
- **Uniform Bucket-Level Access:** Enabled
- **Retention:** 604800 seconds (7 days)
- **Status:** ✅ Active with content

### 2. State Management Bucket
- **Name:** `nvidia-blog-agent-state`
- **Purpose:** Stores application state, ingestion history, and session data
- **State File:** `gs://nvidia-blog-agent-state/state.json`
- **Status:** ✅ Active (currently empty)

### 3. Cloud Build Bucket
- **Name:** `nvidia-blog-agent_cloudbuild`
- **Purpose:** Cloud Build artifacts and logs
- **Status:** ✅ Active

---

## 🗓️ Cloud Scheduler

### Scheduled Job
- **Name:** `nvidia-blog-daily-ingest`
- **Region:** `us-central1`
- **Schedule:** `0 7 * * *` (7:00 AM daily, America/New_York timezone)
- **Target Type:** HTTP
- **Target:** Cloud Run service `nvidia-blog-agent` `/ingest` endpoint
- **Status:** ✅ ENABLED

---

## 🐳 Artifact Registry

### Docker Repository
- **Name:** `nvidia-blog-agent`
- **Format:** DOCKER
- **Mode:** STANDARD_REPOSITORY
- **Location:** `us-central1`
- **Description:** Container images for NVIDIA Blog Agent
- **Size:** 155.347 MB
- **Encryption:** Google-managed key
- **Created:** 2025-11-24T17:58:35
- **Updated:** 2025-11-24T19:38:43

### Container Images
- **Latest:** `us-central1-docker.pkg.dev/nvidia-blog-agent/nvidia-blog-agent/nvidia-blog-agent:latest`

---

## 🔐 IAM Service Accounts

### 1. Compute Engine Default Service Account
- **Email:** `262844214274-compute@developer.gserviceaccount.com`
- **Status:** ✅ Active
- **OAuth2 Client ID:** `101617961705943123051`

### 2. NVIDIA Blog Agent Service Account
- **Email:** `nvidia-blog-agent-sa@nvidia-blog-agent.iam.gserviceaccount.com`
- **Display Name:** NVIDIA Blog Agent Service Account
- **Status:** ✅ Active
- **OAuth2 Client ID:** `115863459349437962035`
- **Used By:** Cloud Run service

---

## 🔍 Vertex AI Resources

### RAG Corpus
- **Corpus ID:** `6917529027641081856`
- **Location:** `us-east5`
- **Status:** ✅ Active

### Gemini Model
- **Model:** `gemini-2.0-flash-001`
- **Location:** `us-east5`
- **Usage:** QA generation and summarization

### AI Endpoints
- **Status:** None configured (using Vertex AI API directly)

### Index Endpoints
- **Status:** None configured (using RAG corpus)

---

## 📊 Logging

### Available Logs
1. `cloudaudit.googleapis.com/activity` - Audit activity logs
2. `cloudaudit.googleapis.com/system_event` - System event logs
3. `cloudbuild` - Cloud Build logs
4. `cloudscheduler.googleapis.com/executions` - Scheduler execution logs
5. `run.googleapis.com/requests` - Cloud Run request logs
6. `run.googleapis.com/stderr` - Cloud Run stderr logs
7. `run.googleapis.com/varlog/system` - Cloud Run system logs

---

## 🔌 Enabled APIs

The following Google Cloud APIs are enabled in the project:

### Core Services
- ✅ Cloud Run API (`run.googleapis.com`)
- ✅ Cloud Storage API (`storage.googleapis.com`)
- ✅ Cloud Scheduler API (`cloudscheduler.googleapis.com`)
- ✅ Artifact Registry API (`artifactregistry.googleapis.com`)
- ✅ Cloud Build API (`cloudbuild.googleapis.com`)
- ✅ Container Registry API (`containerregistry.googleapis.com`)

### AI/ML Services
- ✅ Vertex AI API (`aiplatform.googleapis.com`)
- ✅ Discovery Engine API (`discoveryengine.googleapis.com`)
- ✅ Vision AI API (`visionai.googleapis.com`)

### Security & Identity
- ✅ Identity and Access Management API (`iam.googleapis.com`)
- ✅ Security Token Service API (`sts.googleapis.com`)
- ✅ Service Usage API (`serviceusage.googleapis.com`)

### Monitoring & Logging
- ✅ Cloud Logging API (`logging.googleapis.com`)
- ✅ Cloud Monitoring API (`monitoring.googleapis.com`)
- ✅ Telemetry API (`telemetry.googleapis.com`)

### Other Services
- ✅ Service Management API (`servicemanagement.googleapis.com`)
- ✅ Cloud Datastore API (`datastore.googleapis.com`)
- ✅ Cloud SQL Component API (`sql-component.googleapis.com`)
- ✅ Deployment Manager API (`deploymentmanager.googleapis.com`)
- ✅ Dataflow API (`dataflow.googleapis.com`)
- ✅ Dataform API (`dataform.googleapis.com`)
- ✅ Data Lineage API (`datalineage.googleapis.com`)
- ✅ Cloud Dataplex API (`dataplex.googleapis.com`)

### Disabled APIs (Not Currently Used)
- ❌ Cloud Functions API (`cloudfunctions.googleapis.com`)
- ❌ Workflows API (`workflows.googleapis.com`)

---

## 🏗️ Infrastructure Summary

### Compute
- **Cloud Run:** 1 service (nvidia-blog-agent)
- **Compute Engine:** 0 instances
- **Cloud Functions:** 0 functions

### Storage
- **Cloud Storage:** 3 buckets
- **BigQuery:** Not configured
- **Cloud Datastore:** Not configured

### Networking
- **VPCs:** Default VPC
- **Load Balancers:** Cloud Run managed

### Messaging
- **Pub/Sub Topics:** 0 topics
- **Pub/Sub Subscriptions:** 0 subscriptions

### Orchestration
- **Cloud Scheduler:** 1 job
- **Cloud Workflows:** Not configured

---

## 🔄 Architecture Flow

```
Cloud Scheduler (Daily 7 AM)
    ↓
Cloud Run Service (/ingest)
    ↓
RSS Feed Discovery → Content Scraping → Summarization
    ↓
Vertex AI RAG Corpus (Ingestion)
    ↓
Cloud Storage (nvidia-blog-rag-docs)
    ↓
State Management (nvidia-blog-agent-state)
```

```
User Query
    ↓
Cloud Run Service (/ask)
    ↓
Vertex AI RAG Retrieval
    ↓
Gemini QA Model (gemini-2.0-flash-001)
    ↓
Response with Sources
```

---

## 📝 Notes

1. **MCP Server:** Currently runs locally via stdio, connecting to Cloud Run REST API. Could be enhanced to run as HTTP/SSE endpoint on Cloud Run.

2. **Vertex AI Location:** Using `us-east5` for RAG and Gemini, while Cloud Run is in `us-central1`. This is acceptable for API calls.

3. **State Management:** State is stored in Cloud Storage, enabling stateless Cloud Run instances.

4. **Security:** 
   - API key protection on `/ingest` endpoint
   - Service account with least privilege
   - No public access to storage buckets

5. **Monitoring:** Cloud Logging and Monitoring are enabled and collecting metrics.

6. **Scaling:** Cloud Run auto-scales from 0 to 100 instances based on traffic.

---

## 🔗 Quick Links

- **Cloud Console:** https://console.cloud.google.com/project/nvidia-blog-agent
- **Cloud Run Service:** https://console.cloud.google.com/run/detail/us-central1/nvidia-blog-agent
- **Cloud Storage:** https://console.cloud.google.com/storage/browser?project=nvidia-blog-agent
- **Cloud Scheduler:** https://console.cloud.google.com/cloudscheduler?project=nvidia-blog-agent
- **Artifact Registry:** https://console.cloud.google.com/artifacts?project=nvidia-blog-agent
- **Vertex AI:** https://console.cloud.google.com/vertex-ai?project=nvidia-blog-agent
- **Logs:** https://console.cloud.google.com/logs?project=nvidia-blog-agent

---

## 🚀 Deployment Information

- **Deployment Method:** Cloud Build + Artifact Registry
- **CI/CD:** Automated via Cloud Build triggers
- **Container Registry:** Artifact Registry (us-central1)
- **Latest Deployment:** 2025-11-25T00:39:29.144391Z

---

*This inventory is automatically generated from gcloud commands. Update manually as infrastructure changes.*

