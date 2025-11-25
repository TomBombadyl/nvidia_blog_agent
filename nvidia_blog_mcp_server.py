"""MCP server for NVIDIA Blog Agent.

This server provides MCP tools that connect to the deployed Cloud Run service.
It runs over stdio and can be used by any MCP-capable host.
"""

import asyncio
import os
from typing import Any, Dict

import httpx
from dotenv import load_dotenv

from mcp import types as mcp_types
from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

load_dotenv()

SERVICE_URL = os.environ.get("NVIDIA_BLOG_SERVICE_URL")  # Cloud Run URL
INGEST_API_KEY = os.environ.get("INGEST_API_KEY")  # same value as the secret

if not SERVICE_URL:
    raise RuntimeError("NVIDIA_BLOG_SERVICE_URL must be set")

app = Server("nvidia-blog-agent-mcp")


@app.initialize()
async def initialize(
    params: mcp_types.InitializationParams,
) -> InitializationOptions:
    return InitializationOptions(
        server_name="nvidia-blog-agent-mcp",
        server_version="0.1.0",
        capabilities=mcp_types.ServerCapabilities(
            tools=True,
        ),
    )


@app.list_tools()
async def list_tools() -> mcp_types.ListToolsResult:
    """
    Advertise two tools:
      - ask_nvidia_blog (read-only)
      - trigger_ingest (write, protected)
    """
    tools = [
        mcp_types.Tool(
            name="ask_nvidia_blog",
            description="Ask questions about NVIDIA Tech Blogs using the deployed RAG agent.",
            input_schema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "User question about NVIDIA tech blogs.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of documents to retrieve (recommended 8–10).",
                        "minimum": 1,
                        "maximum": 20,
                        "default": 8,
                    },
                },
                "required": ["question"],
            },
            # readOnlyHint is advisory; host may use it in safety logic
            properties={"readOnlyHint": True},
        ),
        mcp_types.Tool(
            name="trigger_ingest",
            description=(
                "Trigger a new ingestion run against the NVIDIA Tech Blog feed. "
                "Uses the protected /ingest endpoint on the Cloud Run service."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "force": {
                        "type": "boolean",
                        "description": "Optional flag; currently ignored by backend.",
                        "default": False,
                    }
                },
            },
            properties={"readOnlyHint": False},
        ),
    ]
    return mcp_types.ListToolsResult(tools=tools)


async def call_cloud_run_ask(question: str, top_k: int) -> Dict[str, Any]:
    """Call the Cloud Run /ask endpoint."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{SERVICE_URL}/ask",
            json={"question": question, "top_k": top_k},
        )
        resp.raise_for_status()
        return resp.json()


async def call_cloud_run_ingest() -> Dict[str, Any]:
    """Call the Cloud Run /ingest endpoint with API key."""
    headers = {"Content-Type": "application/json"}
    if INGEST_API_KEY:
        headers["X-API-Key"] = INGEST_API_KEY

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(
            f"{SERVICE_URL}/ingest",
            json={},
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> mcp_types.CallToolResult:
    try:
        if name == "ask_nvidia_blog":
            question = arguments.get("question", "").strip()
            if not question:
                raise ValueError("Missing 'question' parameter")
            top_k = int(arguments.get("top_k", 8))
            data = await call_cloud_run_ask(question, top_k)
            answer = data.get("answer", "")
            sources = data.get("sources", [])
            text_parts = [answer]
            if sources:
                text_parts.append("\n\nSources:\n")
                for s in sources:
                    title = s.get("title") or "Unknown title"
                    url = s.get("url") or "N/A"
                    text_parts.append(f"- {title} — {url}")
            content = mcp_types.TextContent(
                type="text",
                text="".join(text_parts),
            )
            return mcp_types.CallToolResult(content=[content])

        elif name == "trigger_ingest":
            data = await call_cloud_run_ingest()
            content = mcp_types.TextContent(
                type="text",
                text=f"Ingestion triggered.\n\nResponse:\n{data}",
            )
            return mcp_types.CallToolResult(content=[content])

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        # Return MCP error content rather than crashing the server
        err_text = f"Error calling tool '{name}': {e}"
        content = mcp_types.TextContent(type="text", text=err_text)
        return mcp_types.CallToolResult(content=[content])


async def main() -> None:
    """Run as stdio server so any MCP host can spawn it."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            NotificationOptions(),
        )


if __name__ == "__main__":
    asyncio.run(main())
