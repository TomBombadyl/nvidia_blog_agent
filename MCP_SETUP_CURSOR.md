# Setting Up MCP Server for Cursor

## Overview

The NVIDIA Blog Agent includes an MCP (Model Context Protocol) server that exposes the Cloud Run API as tools that Cursor can use. This allows you to query NVIDIA blogs directly from within Cursor.

## Prerequisites

1. **Python environment** with dependencies installed
2. **Environment variables** configured (`.env` file)
3. **Cursor IDE** with MCP support

## Quick Setup

### Step 1: Verify MCP Server File

The MCP server is located at: `nvidia_blog_mcp_server.py`

It provides two tools:
- `ask_nvidia_blog`: Query the RAG system with questions
- `trigger_ingest`: Trigger ingestion of new blog posts

### Step 2: Configure Environment Variables

Create or update your `.env` file:

```bash
# Required: Your Cloud Run service URL
NVIDIA_BLOG_SERVICE_URL=https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app

# Required: Your ingest API key (from deployment)
INGEST_API_KEY=your-api-key-here
```

### Step 3: Configure Cursor MCP Settings

Cursor uses MCP configuration files. You need to add the NVIDIA Blog Agent MCP server to Cursor's configuration.

#### Option A: Using the Existing `mcp.json`

The project includes `mcp.json` which defines the MCP server. However, Cursor typically uses a different location for MCP configs.

#### Option B: Add to Cursor's MCP Config

1. **Find Cursor's MCP config location**:
   - Windows: `%APPDATA%\Cursor\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`
   - macOS: `~/Library/Application Support/Cursor/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`
   - Linux: `~/.config/Cursor/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

2. **Add the NVIDIA Blog Agent server**:

   Open the MCP settings file and add:

   ```json
   {
     "mcpServers": {
       "nvidia-blog-agent": {
         "command": "python",
         "args": [
           "Z:\\SynapGarden\\nvidia_blog_agent\\nvidia_blog_mcp_server.py"
         ],
         "env": {
           "NVIDIA_BLOG_SERVICE_URL": "https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app",
           "INGEST_API_KEY": "your-api-key-here"
         }
       }
     }
   }
   ```

   **Important**: 
   - Replace the path with your actual absolute path to `nvidia_blog_mcp_server.py`
   - Replace `your-api-key-here` with your actual API key
   - On Windows, use forward slashes or escaped backslashes: `Z:/SynapGarden/nvidia_blog_agent/nvidia_blog_mcp_server.py`

#### Option C: Use Environment Variables (Recommended)

Instead of hardcoding in the config, use environment variables:

```json
{
  "mcpServers": {
    "nvidia-blog-agent": {
      "command": "python",
      "args": [
        "Z:/SynapGarden/nvidia_blog_agent/nvidia_blog_mcp_server.py"
      ]
    }
  }
}
```

Then ensure your `.env` file is in the project root and the MCP server will load it via `load_dotenv()`.

### Step 4: Test the MCP Server

1. **Restart Cursor** to load the new MCP configuration

2. **Verify MCP tools are available**:
   - In Cursor, you should see the MCP tools in the available tools list
   - Try using: "Ask the NVIDIA blog agent about RAG"

3. **Test via command line** (optional):
   ```bash
   python nvidia_blog_mcp_server.py
   ```
   This should start the stdio server (it will wait for input).

## Available MCP Tools

### 1. `ask_nvidia_blog`

Query the NVIDIA blog RAG system.

**Parameters**:
- `question` (required): Your question about NVIDIA tech blogs
- `top_k` (optional, default: 8): Number of documents to retrieve (1-20)

**Example usage in Cursor**:
- "Ask the NVIDIA blog agent: What did NVIDIA say about RAG?"
- "Query NVIDIA blogs about CUDA optimization with top_k=10"

### 2. `trigger_ingest`

Trigger ingestion of new blog posts from the feed.

**Parameters**:
- `force` (optional, default: false): Currently ignored by backend

**Example usage in Cursor**:
- "Trigger ingestion of new NVIDIA blog posts"

## Troubleshooting

### MCP Server Not Appearing

1. **Check Python path**: Ensure `python` command works in your terminal
2. **Verify file path**: Use absolute path in MCP config
3. **Check environment variables**: Ensure `.env` file exists and has correct values
4. **Restart Cursor**: MCP servers are loaded at startup

### "Module not found" Errors

Install required dependencies:
```bash
pip install mcp httpx python-dotenv
```

Or install the full project:
```bash
pip install -e .
```

### Connection Errors

1. **Verify service URL**: Check that `NVIDIA_BLOG_SERVICE_URL` is correct
2. **Check API key**: Ensure `INGEST_API_KEY` matches your deployment
3. **Test service directly**: 
   ```bash
   curl https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/health
   ```

### Environment Variables Not Loading

The MCP server uses `load_dotenv()` which looks for `.env` in:
1. Current working directory
2. Parent directories (up to the project root)

Ensure `.env` is in the project root or set environment variables in the MCP config.

## Advanced Configuration

### Custom Python Interpreter

If you use a virtual environment:

```json
{
  "mcpServers": {
    "nvidia-blog-agent": {
      "command": "Z:/SynapGarden/nvidia_blog_agent/venv/Scripts/python.exe",
      "args": [
        "Z:/SynapGarden/nvidia_blog_agent/nvidia_blog_mcp_server.py"
      ]
    }
  }
}
```

### Multiple MCP Servers

You can have multiple MCP servers configured:

```json
{
  "mcpServers": {
    "nvidia-blog-agent": {
      "command": "python",
      "args": ["Z:/SynapGarden/nvidia_blog_agent/nvidia_blog_mcp_server.py"]
    },
    "other-mcp-server": {
      "command": "python",
      "args": ["path/to/other/server.py"]
    }
  }
}
```

## Usage Examples in Cursor

Once configured, you can use the tools in natural language:

1. **Ask questions**:
   - "What did NVIDIA say about transformer optimization?"
   - "Find information about CUDA streams in NVIDIA blogs"
   - "What are the latest developments in RAG according to NVIDIA?"

2. **Trigger ingestion**:
   - "Update the blog database with new posts"
   - "Run ingestion to get latest NVIDIA blog posts"

The MCP server will automatically:
- Format questions properly
- Call the Cloud Run API
- Return formatted answers with sources
- Handle errors gracefully

## Security Notes

- The `INGEST_API_KEY` is required for the `trigger_ingest` tool
- The `ask_nvidia_blog` tool is publicly accessible (no auth needed)
- Keep your `.env` file secure and never commit it to git
- The MCP server runs locally and connects to your Cloud Run service

