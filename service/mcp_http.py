"""HTTP/SSE MCP endpoint for Cloud Run using FastMCP.

This module provides a streamable HTTP transport for the MCP server,
allowing Cursor and other MCP clients to connect directly via URL.

Best practices from official MCP Python SDK:
- Use FastMCP for HTTP/SSE transport
- Mount to existing FastAPI app
- Handle CORS properly
- Use stateless mode for Cloud Run (stateless_http=True)
"""

import json
import logging
import os
from typing import Any, Dict, Optional

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Create FastMCP server instance
# Using stateless mode for Cloud Run (no session persistence needed)
mcp = FastMCP("nvidia-blog-agent-mcp", stateless_http=True)

# Optional API key for MCP endpoint (if org policy requires authentication)
MCP_API_KEY = os.environ.get("MCP_API_KEY")

# Import service components to call directly (avoid HTTP overhead)
# These will be set when the module is imported after service initialization
_qa_agent: Optional[Any] = None
_ingest_client: Optional[Any] = None
_config: Optional[Any] = None

INGEST_API_KEY = os.environ.get("INGEST_API_KEY")


def set_service_components(qa_agent, ingest_client, config):
    """Set service components for direct function calls.
    
    This avoids HTTP overhead when calling from within the same service.
    Called from service/app.py after initialization.
    """
    global _qa_agent, _ingest_client, _config
    _qa_agent = qa_agent
    _ingest_client = ingest_client
    _config = config


async def call_ask_direct(question: str, top_k: int) -> Dict[str, Any]:
    """Call the QA agent directly (within same service)."""
    if _qa_agent is None:
        raise RuntimeError("QA agent not initialized")
    
    answer, retrieved_docs = await _qa_agent.answer(question=question, k=top_k)
    
    sources = [
        {
            "title": doc.title,
            "url": str(doc.url),
            "score": doc.score,
            "snippet": doc.snippet[:200] + "..." if len(doc.snippet) > 200 else doc.snippet,
        }
        for doc in retrieved_docs
    ]
    
    return {
        "answer": answer,
        "sources": sources,
        "session_id": None,
        "cached": False,
    }


async def call_ingest_direct() -> Dict[str, Any]:
    """Call the ingestion pipeline directly (within same service).
    
    Requires INGEST_API_KEY to be configured for security.
    """
    # Security: Require API key even for internal calls
    if not INGEST_API_KEY:
        raise RuntimeError("Ingestion requires authentication. INGEST_API_KEY must be configured.")
    
    if _ingest_client is None or _config is None:
        raise RuntimeError("Ingestion service not initialized")
    
    # Import here to avoid circular dependencies
    from nvidia_blog_agent.agents.workflow import run_ingestion_pipeline
    from nvidia_blog_agent.agents.gemini_summarizer import GeminiSummarizer
    from nvidia_blog_agent.tools.http_fetcher import HttpHtmlFetcher, fetch_feed_html
    from nvidia_blog_agent.context.session_config import (
        get_existing_ids_from_state,
        update_existing_ids_in_state,
        store_last_ingestion_result_metadata,
    )
    from nvidia_blog_agent.context.compaction import (
        append_ingestion_history_entry,
        compact_ingestion_history,
        get_last_ingestion_result_metadata,
    )
    from nvidia_blog_agent.context.state_persistence import load_state, save_state
    
    state_path = os.environ.get("STATE_PATH", "state.json")
    state = load_state(state_path)
    existing_ids = get_existing_ids_from_state(state)
    
    feed_html = await fetch_feed_html()
    fetcher = HttpHtmlFetcher()
    summarizer = GeminiSummarizer(_config.gemini)
    
    result = await run_ingestion_pipeline(
        feed_html=feed_html,
        existing_ids=existing_ids,
        fetcher=fetcher,
        summarizer=summarizer,
        rag_client=_ingest_client,
    )
    
    update_existing_ids_in_state(state, result.new_posts)
    store_last_ingestion_result_metadata(state, result)
    
    metadata = get_last_ingestion_result_metadata(state)
    append_ingestion_history_entry(state, metadata)
    compact_ingestion_history(state, max_entries=10)
    
    save_state(state, state_path)
    
    return {
        "discovered_count": len(result.discovered_posts),
        "new_count": len(result.new_posts),
        "ingested_count": len(result.summaries),
        "message": f"Successfully processed {len(result.new_posts)} new posts",
    }


@mcp.tool()
async def ask_nvidia_blog(question: str, top_k: int = 8) -> str:
    """Ask questions about NVIDIA Tech Blogs using the deployed RAG agent.
    
    Args:
        question: User question about NVIDIA tech blogs
        top_k: Number of documents to retrieve (1-20, default: 8)
    
    Returns:
        Answer with sources formatted as text
    """
    try:
        if not question or not question.strip():
            return "Error: Question cannot be empty"
        
        top_k = max(1, min(20, int(top_k)))
        
        # Call directly if available, otherwise fall back to HTTP
        if _qa_agent is not None:
            data = await call_ask_direct(question.strip(), top_k)
        else:
            # Fallback to HTTP if service not initialized
            import httpx
            service_url = os.environ.get("NVIDIA_BLOG_SERVICE_URL", "http://localhost:8080")
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{service_url}/ask",
                    json={"question": question.strip(), "top_k": top_k},
                )
                resp.raise_for_status()
                data = resp.json()
        
        answer = data.get("answer", "")
        sources = data.get("sources", [])
        
        text_parts = [answer]
        if sources:
            text_parts.append("\n\nSources:\n")
            for s in sources:
                title = s.get("title") or "Unknown title"
                url = s.get("url") or "N/A"
                text_parts.append(f"- {title} — {url}")
        
        return "".join(text_parts)
    
    except Exception as e:
        logger.exception("Error calling ask_nvidia_blog tool")
        return f"Error: {str(e)}"


@mcp.tool()
async def trigger_ingest(force: bool = False) -> str:
    """Trigger a new ingestion run against the NVIDIA Tech Blog feed.
    
    **REQUIRES AUTHENTICATION:** This tool requires the INGEST_API_KEY to be configured.
    Ingestion is protected to prevent unauthorized access.
    
    Args:
        force: Optional flag; currently ignored by backend (default: False)
    
    Returns:
        Status message with ingestion results
    
    Raises:
        Error if INGEST_API_KEY is not configured
    """
    # Security check: Require API key for ingestion
    if not INGEST_API_KEY:
        return "Error: Ingestion requires authentication. INGEST_API_KEY must be configured in the service."
    
    try:
        # Call directly if available, otherwise fall back to HTTP
        if _ingest_client is not None and _config is not None:
            data = await call_ingest_direct()
        else:
            # Fallback to HTTP if service not initialized
            import httpx
            service_url = os.environ.get("NVIDIA_BLOG_SERVICE_URL", "http://localhost:8080")
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": INGEST_API_KEY  # Always include API key
            }
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(
                    f"{service_url}/ingest",
                    json={},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        
        discovered = data.get("discovered_count", 0)
        new = data.get("new_count", 0)
        ingested = data.get("ingested_count", 0)
        message = data.get("message", "Ingestion completed")
        
        result = f"Ingestion triggered successfully.\n\n"
        result += f"Results:\n"
        result += f"- Discovered: {discovered} posts\n"
        result += f"- New: {new} posts\n"
        result += f"- Ingested: {ingested} summaries\n"
        result += f"- Status: {message}"
        
        return result
    
    except Exception as e:
        logger.exception("Error calling trigger_ingest tool")
        return f"Error: {str(e)}"


class MCPAuthMiddleware(BaseHTTPMiddleware):
    """Optional authentication middleware for MCP endpoint.
    
    If MCP_API_KEY is set, requires X-API-Key header.
    If not set, allows unauthenticated access (requires Cloud Run IAM policy).
    """
    
    async def dispatch(self, request: Request, call_next):
        # Skip auth if no API key configured
        if not MCP_API_KEY:
            return await call_next(request)
        
        # Check for API key in header
        api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").replace("Bearer ", "")
        
        if api_key != MCP_API_KEY:
            return Response(
                content=json.dumps({"error": "Invalid or missing API key"}),
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
            )
        
        return await call_next(request)


def get_mcp_app():
    """Get the FastMCP ASGI app for mounting to FastAPI.
    
    Returns:
        ASGI app that handles MCP protocol over streamable HTTP
        with optional authentication middleware
    """
    # FastMCP streamable_http_app() returns an ASGI app that can be mounted
    # It handles both POST (streamable HTTP) and GET (SSE) requests
    mcp_app = mcp.streamable_http_app()
    
    # Wrap with auth middleware if API key is configured
    if MCP_API_KEY:
        from starlette.applications import Starlette
        # Create a wrapper app with middleware
        wrapped_app = Starlette()
        wrapped_app.add_middleware(MCPAuthMiddleware)
        # Mount the MCP app
        wrapped_app.mount("/", mcp_app)
        return wrapped_app
    
    return mcp_app

