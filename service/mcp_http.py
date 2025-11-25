"""HTTP/SSE MCP endpoint for Cloud Run using FastMCP.

This module provides a streamable HTTP transport for the MCP server,
allowing Cursor and other MCP clients to connect directly via URL.

Best practices from official MCP Python SDK:
- Use FastMCP for HTTP/SSE transport
- Mount to existing FastAPI app
- Handle CORS properly
- Use stateless mode for Cloud Run (stateless_http=True)

This endpoint uses Vertex AI RAG and Gemini directly (same as the stdio server).
"""

import logging
import os
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Create FastMCP server instance
# Using stateless mode for Cloud Run (no session persistence needed)
# Server name matches the stdio server for consistency
mcp = FastMCP("nvidia-blog-mcp", stateless_http=True)

# Don't set streamable_http_path - let it use default
# When mounted at /mcp, endpoints will be at /mcp/mcp by default
# This is the standard MCP pattern

# Import service components to call directly (avoid HTTP overhead)
# These will be set when the module is imported after service initialization
_qa_agent: Optional[Any] = None
_ingest_client: Optional[Any] = None
_config: Optional[Any] = None


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


@mcp.tool()
async def ask_nvidia_blog(question: str, top_k: int = 8) -> str:
    """Ask questions about NVIDIA Tech Blogs using Vertex AI RAG and Gemini (direct API calls, fast).
    
    This tool uses Vertex AI RAG and Gemini directly, bypassing Cloud Run for faster responses.
    
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
        
        # Use the QA agent initialized in the service (uses Vertex AI RAG directly)
        if _qa_agent is None:
            raise RuntimeError(
                "QA agent not initialized. Make sure USE_VERTEX_RAG=true, "
                "RAG_CORPUS_ID, VERTEX_LOCATION, and GEMINI_MODEL_NAME are set."
            )
        
        # Call directly - this uses Vertex AI RAG and Gemini (same as stdio server)
        data = await call_ask_direct(question.strip(), top_k)
        
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


# Authentication middleware removed - service is now public-facing
# MCP endpoint is accessible without authentication


def get_mcp_app():
    """Get the FastMCP ASGI app for mounting to FastAPI.
    
    Returns:
        ASGI app that handles MCP protocol over streamable HTTP
        Public-facing, no authentication required
    """
    from starlette.responses import Response
    
    # Get the base MCP app
    mcp_base_app = mcp.streamable_http_app()
    
    # Wrap it to handle errors gracefully
    async def mcp_wrapper(scope, receive, send):
        try:
            await mcp_base_app(scope, receive, send)
        except Exception as e:
            # If the MCP app fails, return a proper error response
            # This prevents 502 errors from propagating
            logger.exception("Error in MCP app")
            response = Response(
                status_code=400,
                content=f"Invalid MCP request: {str(e)}",
                media_type="text/plain"
            )
            await response(scope, receive, send)
    
    return mcp_wrapper

