"""MCP server for NVIDIA Blog Agent.

This server provides MCP tools that connect directly to Vertex AI RAG and Gemini,
bypassing Cloud Run for faster, more reliable responses.
It runs over stdio and can be used by any MCP-capable host.
"""

import asyncio
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from mcp import types as mcp_types
from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

load_dotenv()

# Initialize server first - don't fail on import
app = Server("nvidia-blog-mcp")

# Lazy initialization of RAG and QA clients
_rag_client = None
_qa_model = None
_qa_agent = None


@app.list_tools()
async def list_tools() -> list[mcp_types.Tool]:
    """
    Advertise the ask_nvidia_blog tool (read-only).
    Ingestion is handled automatically by Cloud Scheduler.
    """
    return [
        mcp_types.Tool(
            name="ask_nvidia_blog",
            description="Ask questions about NVIDIA Tech Blogs using Vertex AI RAG and Gemini (direct API calls, fast).",
            inputSchema={
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
            annotations=mcp_types.ToolAnnotations(readOnlyHint=True),
        ),
    ]


def _initialize_clients():
    """Initialize Vertex AI RAG and Gemini QA clients (lazy initialization)."""
    global _rag_client, _qa_model, _qa_agent
    
    if _qa_agent is not None:
        return  # Already initialized
    
    try:
        from nvidia_blog_agent.config import load_config_from_env
        from nvidia_blog_agent.rag_clients import create_rag_clients
        from nvidia_blog_agent.agents.qa_agent import QAAgent
        from nvidia_blog_agent.agents.gemini_qa_model import GeminiQaModel
        
        # Load configuration from environment
        config = load_config_from_env()
        
        # Create RAG clients (we only need retrieve client)
        _, retrieve_client = create_rag_clients(config)
        _rag_client = retrieve_client
        
        # Create QA model and agent
        qa_model = GeminiQaModel(config.gemini)
        _qa_agent = QAAgent(rag_client=retrieve_client, model=qa_model)
        
    except Exception as e:
        raise RuntimeError(
            f"Failed to initialize RAG/QA clients: {e}. "
            "Make sure USE_VERTEX_RAG=true, RAG_CORPUS_ID, VERTEX_LOCATION, "
            "and GEMINI_MODEL_NAME are set in your environment."
        )


async def ask_question_direct(question: str, top_k: int) -> Dict[str, Any]:
    """Ask a question directly using Vertex AI RAG and Gemini (bypasses Cloud Run)."""
    # Initialize clients if needed
    _initialize_clients()
    
    if _qa_agent is None:
        raise RuntimeError("QA agent not initialized")
    
    # Use QA agent to answer the question
    answer, retrieved_docs = await _qa_agent.answer(question=question, k=top_k)
    
    # Format sources
    sources = [
        {
            "title": doc.title,
            "url": str(doc.url),
            "score": doc.score,
        }
        for doc in retrieved_docs
    ]
    
    return {
        "answer": answer,
        "sources": sources,
    }


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> mcp_types.CallToolResult:
    """Handle tool calls by returning CallToolResult directly."""
    try:
        if name == "ask_nvidia_blog":
            question = arguments.get("question", "").strip()
            if not question:
                raise ValueError("Missing 'question' parameter")
            top_k = int(arguments.get("top_k", 8))
            
            # Call Vertex AI RAG and Gemini directly (much faster than Cloud Run)
            data = await ask_question_direct(question, top_k)
            answer = data.get("answer", "")
            sources = data.get("sources", [])
            text_parts = [answer]
            if sources:
                text_parts.append("\n\nSources:\n")
                for s in sources:
                    title = s.get("title") or "Unknown title"
                    url = s.get("url") or "N/A"
                    text_parts.append(f"- {title} — {url}")
            
            # Return CallToolResult following official MCP SDK pattern
            # Explicitly construct TextContent with only required fields
            text_content = mcp_types.TextContent(
                type="text",
                text="".join(text_parts)
            )
            return mcp_types.CallToolResult(
                content=[text_content]
            )

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        # Return MCP error content rather than crashing the server
        err_text = f"Error calling tool '{name}': {e}"
        error_content = mcp_types.TextContent(
            type="text",
            text=err_text
        )
        return mcp_types.CallToolResult(
            content=[error_content],
            isError=True
        )


async def main() -> None:
    """Run as stdio server so any MCP host can spawn it."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="nvidia-blog-mcp",
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())

