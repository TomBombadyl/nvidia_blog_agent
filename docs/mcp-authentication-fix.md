# Fixing MCP 403 Forbidden Error

If you're getting a `403 Forbidden` error when connecting to the MCP endpoint, the Cloud Run service requires authentication configuration.

## Problem

Cloud Run services require IAM policy configuration to allow access. The error:
```
403 Forbidden - Your client does not have permission to get URL /mcp from this server
```

Indicates the service doesn't have public access configured.

## Solution Options

### Option 1: Allow Unauthenticated Access (Recommended if allowed by org policy)

Run this command to grant public access:

```bash
gcloud run services add-iam-policy-binding nvidia-blog-agent \
  --region=us-central1 \
  --member="allUsers" \
  --role="roles/run.invoker" \
  --project=nvidia-blog-agent
```

**Note:** If you get an error about organization policy, your GCP organization has restricted public access. Use Option 2 or 3 instead.

### Option 2: Use Service Account Authentication

If your organization blocks public access, you can authenticate using a service account:

1. **Create a service account key:**
```bash
gcloud iam service-accounts keys create mcp-key.json \
  --iam-account=nvidia-blog-agent-sa@nvidia-blog-agent.iam.gserviceaccount.com \
  --project=nvidia-blog-agent
```

2. **Update mcp.json to use service account:**
```json
"nvidia-blog-agent": {
  "url": "https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/mcp",
  "headers": {
    "Authorization": "Bearer $(gcloud auth print-identity-token)"
  }
}
```

**Note:** This requires `gcloud` CLI to be installed and authenticated.

### Option 3: Use API Key Authentication

The service supports optional API key authentication via the `MCP_API_KEY` environment variable.

1. **Set the API key in Cloud Run:**
```bash
gcloud run services update nvidia-blog-agent \
  --region=us-central1 \
  --set-env-vars="MCP_API_KEY=your-secret-api-key-here" \
  --project=nvidia-blog-agent
```

2. **Update mcp.json:**
```json
"nvidia-blog-agent": {
  "url": "https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/mcp",
  "headers": {
    "X-API-Key": "your-secret-api-key-here"
  }
}
```

### Option 4: Grant Access to Specific Users/Groups

If you want to restrict access to specific users or groups:

```bash
# Grant access to a specific user
gcloud run services add-iam-policy-binding nvidia-blog-agent \
  --region=us-central1 \
  --member="user:your-email@example.com" \
  --role="roles/run.invoker" \
  --project=nvidia-blog-agent

# Or grant to a Google Group
gcloud run services add-iam-policy-binding nvidia-blog-agent \
  --region=us-central1 \
  --member="group:your-group@example.com" \
  --role="roles/run.invoker" \
  --project=nvidia-blog-agent
```

## Verify Access

After configuring access, test the endpoint:

```bash
# Test without auth (if public access is enabled)
curl https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/mcp

# Test with API key
curl -H "X-API-Key: your-key" https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/mcp

# Test with identity token
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/mcp
```

## Check Current IAM Policy

To see who currently has access:

```bash
gcloud run services get-iam-policy nvidia-blog-agent \
  --region=us-central1 \
  --project=nvidia-blog-agent
```

## Troubleshooting

### Organization Policy Blocks Public Access

If you see:
```
ERROR: Policy modification failed... perhaps due to an organization policy
```

Your GCP organization has a policy that blocks public Cloud Run access. You must:
1. Contact your GCP administrator to request an exception
2. Use service account or API key authentication (Options 2 or 3)
3. Use the local stdio server instead (see `docs/mcp-setup.md`)

### Service Not Deployed

If the service doesn't exist, deploy it first:

```bash
# See deployment instructions in docs/deployment.md
# Or use the CI/CD pipeline
```

### Still Getting 403 After Configuration

1. Wait a few seconds for IAM policy to propagate
2. Clear Cursor's MCP cache and restart
3. Check Cloud Run logs: `gcloud logging read "resource.type=cloud_run_revision" --limit=50`

