# MCP Setup for Cursor

Complete guide for setting up the NVIDIA Blog Agent MCP server in Cursor IDE.

## Quick Setup

### Option 1: HTTP/SSE Endpoint (Recommended)

The Cloud Run service now exposes an HTTP/SSE MCP endpoint that Cursor can connect to directly. This is the recommended approach as it requires no local setup.

**1. Copy Configuration**

Copy `mcp.json` from the project root to `.cursor/mcp.json`:

```powershell
Copy-Item mcp.json .cursor\mcp.json
```

**2. Verify Configuration**

The configuration should already be set up with the Cloud Run URL:

```json
"nvidia-blog-agent": {
  "url": "https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/mcp",
  "headers": {}
}
```

If the service requires authentication (due to organization policy), add an API key:

```json
"nvidia-blog-agent": {
  "url": "https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/mcp",
  "headers": {
    "X-API-Key": "your-mcp-api-key-here"
  }
}
```

**Note:** If you get a 403 Forbidden error, the service may require authentication. Contact your GCP administrator to either:
- Allow unauthenticated access: `gcloud run services add-iam-policy-binding nvidia-blog-agent --region=us-central1 --member="allUsers" --role="roles/run.invoker"`
- Or configure an API key by setting `MCP_API_KEY` environment variable in Cloud Run

**3. Restart Cursor**

Restart Cursor IDE to load the MCP configuration. The MCP server will connect directly to Cloud Run via HTTP/SSE.

### Option 2: Local Stdio Server (Legacy)

If you prefer to run a local MCP server that connects to Cloud Run:

**1. Copy Configuration**

Copy `mcp.json` from the project root to `.cursor/mcp.json`.

**2. Update Configuration**

Change the `nvidia-blog-agent` entry to use the local stdio server:

```json
"nvidia-blog-agent": {
  "command": "python",
  "args": ["-u", "run_mcp_server.py"],
  "env": {
    "NVIDIA_BLOG_SERVICE_URL": "https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app",
    "INGEST_API_KEY": "your-api-key-here"
  }
}
```

**3. Install Dependencies**

Ensure MCP dependencies are installed:

```powershell
pip install mcp httpx python-dotenv
```

### 4. Restart Cursor

Restart Cursor IDE to load the MCP configuration.

## Testing

### Smoke Test Payload

Use this payload to test the `ask_nvidia_blog` tool:

```json
{
  "question": "Give me a one-sentence summary of what this NVIDIA Tech Blog Intelligence Agent does.",
  "top_k": 4
}
```

### Verify Configuration

Run the test script:

```powershell
python test_mcp_config.py
```

## Available Tools

### `ask_nvidia_blog`
Read-only QA tool for querying NVIDIA Tech Blogs.

**Parameters:**
- `question` (required): Your question about NVIDIA tech blogs
- `top_k` (optional, default: 8): Number of documents to retrieve (1-20)

### `trigger_ingest`
Trigger ingestion of new blog posts (requires API key).

**Parameters:**
- `force` (optional, default: false): Currently ignored by backend

## Troubleshooting

### HTTP/SSE Connection Issues

**Error:** Connection refused or timeout

**Solution:**
- Verify Cloud Run service is deployed and running
- Check the URL in `.cursor/mcp.json` matches your deployed service
- Ensure Cloud Run service allows unauthenticated access (or configure authentication)
- Test the endpoint: `curl https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/mcp`

**Error:** CORS errors in browser

**Solution:** The service is configured with CORS middleware. If issues persist:
- Check `CORS_ORIGINS` environment variable in Cloud Run
- Verify `Mcp-Session-Id` header is exposed (already configured)

### Local Stdio Server Issues

**Error:** `can't open file 'C:\\Users\\...\\nvidia_blog_mcp_server.py'`

**Solution:** Use the wrapper script `run_mcp_server.py` which auto-detects paths, or use absolute path in `.cursor/mcp.json` args field.

**Error:** `ModuleNotFoundError` or `AttributeError`

**Solution:** Install dependencies:
```powershell
pip install mcp httpx python-dotenv
```

### Service Unreachable

**Error:** 403 Forbidden or connection errors

**Solution:** 
- Verify `NVIDIA_BLOG_SERVICE_URL` is correct
- Check Cloud Run service is deployed and accessible
- Ensure IAM permissions allow access
- For local stdio server, verify environment variables are set

## Configuration Reference

The `mcp.json` file in the project root contains the complete configuration with all MCP servers. Copy it to `.cursor/mcp.json` and customize as needed.

**HTTP/SSE Configuration (Recommended):**
```json
"nvidia-blog-agent": {
  "url": "https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/mcp",
  "headers": {}
}
```

**Local Stdio Configuration (Legacy):**
```json
"nvidia-blog-agent": {
  "command": "python",
  "args": ["-u", "run_mcp_server.py"],
  "env": {
    "NVIDIA_BLOG_SERVICE_URL": "https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app",
    "INGEST_API_KEY": "your-api-key"
  }
}
```

## Architecture

The MCP server is now available in two modes:

1. **HTTP/SSE Endpoint** (Recommended): Direct connection to Cloud Run service at `/mcp`
   - No local setup required
   - Uses FastMCP with streamable HTTP transport
   - Stateless mode for Cloud Run scalability
   - Automatic session management

2. **Local Stdio Server**: Runs locally, connects to Cloud Run REST API
   - Requires local Python environment
   - Useful for development or when HTTP access is restricted
   - Uses `run_mcp_server.py` wrapper for path resolution
