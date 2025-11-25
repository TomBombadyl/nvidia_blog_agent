"""FastAPI HTTP service for NVIDIA Blog Agent.

This service provides REST API endpoints for:
- POST /ask: Answer questions using RAG retrieval + Gemini QA
- POST /ingest: Trigger ingestion pipeline to discover and ingest new blog posts
- POST /ask/batch: Batch query endpoint
- GET /analytics: Usage analytics endpoint
- GET /history: Query history endpoint
- GET /export: Export functionality (CSV/JSON)
- GET /admin/stats: Admin dashboard endpoints

The service is designed for Cloud Run deployment with:
- Application Default Credentials (no JSON keys in production)
- Environment-based configuration
- Proper error handling and logging
- Security best practices (optional API key protection for /ingest)
- Monitoring and observability
- Rate limiting
- Response caching
- Multi-turn conversation support
"""

import os
import time
import csv
import json
import logging
from typing import Optional, List
from contextlib import asynccontextmanager
from io import StringIO

from fastapi import FastAPI, HTTPException, status, Header, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.routing import Mount
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from nvidia_blog_agent.config import load_config_from_env
from nvidia_blog_agent.rag_clients import create_rag_clients
from nvidia_blog_agent.agents.qa_agent import QAAgent
from nvidia_blog_agent.agents.gemini_qa_model import GeminiQaModel
from nvidia_blog_agent.agents.workflow import run_ingestion_pipeline
from nvidia_blog_agent.agents.gemini_summarizer import GeminiSummarizer
from nvidia_blog_agent.tools.http_fetcher import HttpHtmlFetcher, fetch_feed_html
from nvidia_blog_agent.context.session_config import (
    get_existing_ids_from_state,
    update_existing_ids_in_state,
    store_last_ingestion_result_metadata,
    get_last_ingestion_result_metadata,
)
from nvidia_blog_agent.context.compaction import (
    append_ingestion_history_entry,
    compact_ingestion_history,
)
from nvidia_blog_agent.context.state_persistence import load_state, save_state
from nvidia_blog_agent.monitoring import (
    get_metrics_collector,
    create_structured_logger,
    HealthChecker,
)
from nvidia_blog_agent.caching import get_response_cache
from nvidia_blog_agent.session_manager import get_session_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = create_structured_logger(__name__)

# Global state for initialized clients (initialized at startup)
_qa_agent: Optional[QAAgent] = None
_ingest_client = None
_config = None
_state_path: Optional[str] = None
_health_checker: Optional[HealthChecker] = None
_limiter = Limiter(key_func=get_remote_address)


# Request/Response models
class AskRequest(BaseModel):
    """Request model for /ask endpoint."""

    question: str = Field(..., description="The question to answer", min_length=1)
    top_k: int = Field(
        default=5, ge=1, le=20, description="Number of documents to retrieve"
    )
    session_id: Optional[str] = Field(
        default=None, description="Session ID for multi-turn conversations"
    )
    use_cache: bool = Field(default=True, description="Whether to use response cache")


class AskResponse(BaseModel):
    """Response model for /ask endpoint."""

    answer: str = Field(..., description="The generated answer")
    sources: list[dict] = Field(
        ..., description="List of source documents with title, url, score"
    )
    session_id: Optional[str] = Field(
        default=None, description="Session ID for this conversation"
    )
    cached: bool = Field(
        default=False, description="Whether the response was served from cache"
    )


class BatchAskRequest(BaseModel):
    """Request model for /ask/batch endpoint."""

    questions: List[str] = Field(
        ..., description="List of questions to answer", min_items=1, max_items=10
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of documents to retrieve per question",
    )


class BatchAskResponse(BaseModel):
    """Response model for /ask/batch endpoint."""

    results: List[AskResponse] = Field(..., description="List of answers")


class IngestResponse(BaseModel):
    """Response model for /ingest endpoint."""

    discovered_count: int = Field(..., description="Number of posts found in feed")
    new_count: int = Field(..., description="Number of new posts processed")
    ingested_count: int = Field(..., description="Number of summaries ingested")
    message: str = Field(..., description="Status message")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI startup/shutdown.

    Initializes RAG clients and QA agent at startup.
    """
    global _qa_agent, _ingest_client, _config, _state_path, _health_checker

    try:
        logger.info("Initializing NVIDIA Blog Agent service...")

        # Load configuration from environment
        _config = load_config_from_env()
        logger.info(
            "Service configuration loaded",
            gemini_model=_config.gemini.model_name,
            rag_backend="Vertex AI" if _config.rag.use_vertex_rag else "HTTP",
        )

        # Get state path from environment
        _state_path = os.environ.get("STATE_PATH", "state.json")
        logger.info("State path configured", state_path=_state_path)

        # Create RAG clients
        _ingest_client, retrieve_client = create_rag_clients(_config)

        # Create QA agent
        qa_model = GeminiQaModel(_config.gemini)
        _qa_agent = QAAgent(rag_client=retrieve_client, model=qa_model)

        # Initialize health checker
        _health_checker = HealthChecker()

        # Register dependency health checks
        async def check_rag_backend():
            """Check RAG backend health."""
            try:
                # Simple health check: try to retrieve with a test query
                await retrieve_client.retrieve("test", k=1)
                return True, "RAG backend is accessible"
            except Exception as e:
                return False, f"RAG backend error: {str(e)}"

        async def check_qa_agent():
            """Check QA agent health."""
            return (
                _qa_agent is not None,
                "QA agent initialized" if _qa_agent else "QA agent not initialized",
            )

        _health_checker.register_dependency("rag_backend", check_rag_backend)
        _health_checker.register_dependency("qa_agent", check_qa_agent)

        logger.info("Service initialized successfully")
        
        # Initialize MCP HTTP endpoint with service components
        from service.mcp_http import set_service_components
        set_service_components(_qa_agent, _ingest_client, _config)

        yield

    except Exception as e:
        logger.exception("Failed to initialize service", error=str(e))
        raise
    finally:
        logger.info("Shutting down service...")


# Create FastAPI app with lifespan
app = FastAPI(
    title="NVIDIA Blog Agent API",
    description="REST API for querying NVIDIA Tech Blog content using RAG",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add rate limiting
app.state.limiter = _limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mount MCP HTTP/SSE endpoint
from service.mcp_http import get_mcp_app

# Add CORS middleware (before mounting MCP to ensure it applies)
# Note: MCP requires exposing Mcp-Session-Id header for session management
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],  # Required for MCP session management
)

# Mount MCP server at /mcp endpoint
# FastAPI will route /mcp/* requests to this mount
# Other routes are matched first, so /health, /ingest, etc. won't reach here
app.mount("/mcp", get_mcp_app())


# Middleware for metrics and logging
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Middleware to collect metrics and log requests."""
    start_time = time.time()
    metrics = get_metrics_collector()

    try:
        response = await call_next(request)
        latency_ms = (time.time() - start_time) * 1000

        metrics.record_request(
            endpoint=request.url.path,
            method=request.method,
            status_code=response.status_code,
            latency_ms=latency_ms,
        )

        logger.info(
            "Request processed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=round(latency_ms, 2),
        )

        return response
    except Exception:
        latency_ms = (time.time() - start_time) * 1000
        metrics.record_request(
            endpoint=request.url.path,
            method=request.method,
            status_code=500,
            latency_ms=latency_ms,
        )
        raise


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"service": "NVIDIA Blog Agent API", "status": "healthy", "version": "0.2.0"}


@app.get("/health")
async def health():
    """Health check endpoint with dependency status."""
    if _qa_agent is None or _health_checker is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not initialized",
        )

    health_status = await _health_checker.check_all()
    status_code = (
        status.HTTP_200_OK
        if health_status["status"] == "healthy"
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return JSONResponse(status_code=status_code, content=health_status)


@app.post("/ask", response_model=AskResponse)
@_limiter.limit(os.environ.get("RATE_LIMIT", "10/minute"))
async def ask_question(request: Request, ask_request: AskRequest):
    """Answer a question using RAG retrieval + Gemini QA.

    This endpoint:
    1. Checks cache for cached responses (if enabled)
    2. Retrieves relevant documents from the RAG backend
    3. Generates an answer using Gemini based on retrieved documents
    4. Returns the answer and source documents
    5. Stores query in session history (if session_id provided)

    Args:
        request: FastAPI Request object
        ask_request: AskRequest containing question and optional parameters

    Returns:
        AskResponse with answer and source documents

    Raises:
        HTTPException: If service is not initialized or QA fails
    """
    if _qa_agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="QA agent not initialized",
        )

    start_time = time.time()
    cache = get_response_cache()
    session_manager = get_session_manager()

    try:
        logger.info(
            "Processing question",
            question_preview=ask_request.question[:100],
            session_id=ask_request.session_id,
        )

        # Check cache if enabled
        if ask_request.use_cache:
            cached_response = cache.get(
                "/ask", question=ask_request.question, top_k=ask_request.top_k
            )
            if cached_response:
                logger.info(
                    "Serving from cache", question_preview=ask_request.question[:100]
                )
                return AskResponse(
                    answer=cached_response["answer"],
                    sources=cached_response["sources"],
                    session_id=ask_request.session_id,
                    cached=True,
                )

        # Use QA agent to answer the question
        answer, retrieved_docs = await _qa_agent.answer(
            question=ask_request.question, k=ask_request.top_k
        )

        # Format sources
        sources = [
            {
                "title": doc.title,
                "url": str(doc.url),
                "score": doc.score,
                "snippet": doc.snippet[:200] + "..."
                if len(doc.snippet) > 200
                else doc.snippet,
            }
            for doc in retrieved_docs
        ]

        latency_ms = (time.time() - start_time) * 1000

        # Cache response if enabled
        if ask_request.use_cache:
            cache.set(
                "/ask",
                {"answer": answer, "sources": sources},
                question=ask_request.question,
                top_k=ask_request.top_k,
            )

        # Store in session if session_id provided
        session_id = ask_request.session_id
        if not session_id:
            # Create new session if none provided
            session = session_manager.create_session()
            session_id = session.session_id

        session_manager.add_query_to_session(
            session_id=session_id,
            question=ask_request.question,
            answer=answer,
            sources=sources,
            latency_ms=latency_ms,
        )

        logger.info(
            "Answer generated",
            sources_count=len(sources),
            latency_ms=round(latency_ms, 2),
            session_id=session_id,
        )

        return AskResponse(
            answer=answer, sources=sources, session_id=session_id, cached=False
        )

    except Exception as e:
        logger.exception("Error processing question", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process question: {str(e)}",
        )


@app.post("/ask/batch", response_model=BatchAskResponse)
@_limiter.limit(os.environ.get("BATCH_RATE_LIMIT", "5/minute"))
async def ask_batch(request: Request, batch_request: BatchAskRequest):
    """Answer multiple questions in a single request.

    This endpoint processes multiple questions in parallel and returns
    all answers in a single response.

    Args:
        request: FastAPI Request object
        batch_request: BatchAskRequest containing list of questions

    Returns:
        BatchAskResponse with list of answers

    Raises:
        HTTPException: If service is not initialized or processing fails
    """
    if _qa_agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="QA agent not initialized",
        )

    import asyncio

    try:
        logger.info(
            "Processing batch request", question_count=len(batch_request.questions)
        )

        # Process all questions in parallel
        tasks = [
            _qa_agent.answer(question=q, k=batch_request.top_k)
            for q in batch_request.questions
        ]
        results = await asyncio.gather(*tasks)

        # Format responses
        batch_results = []
        for (answer, docs), question in zip(results, batch_request.questions):
            sources = [
                {
                    "title": doc.title,
                    "url": str(doc.url),
                    "score": doc.score,
                    "snippet": doc.snippet[:200] + "..."
                    if len(doc.snippet) > 200
                    else doc.snippet,
                }
                for doc in docs
            ]
            batch_results.append(
                AskResponse(
                    answer=answer, sources=sources, session_id=None, cached=False
                )
            )

        logger.info(
            "Batch request completed", question_count=len(batch_request.questions)
        )

        return BatchAskResponse(results=batch_results)

    except Exception as e:
        logger.exception("Error processing batch request", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process batch request: {str(e)}",
        )


@app.get("/analytics")
async def get_analytics():
    """Get usage analytics and metrics.

    Returns:
        Dictionary with request metrics, cache stats, and session stats
    """
    metrics = get_metrics_collector()
    cache = get_response_cache()
    session_manager = get_session_manager()

    return {
        "metrics": metrics.get_stats(),
        "cache": cache.get_stats().__dict__,
        "sessions": session_manager.get_stats(),
        "timestamp": time.time(),
    }


@app.get("/history")
async def get_history(
    session_id: Optional[str] = None, limit: int = 50, offset: int = 0
):
    """Get query history.

    Args:
        session_id: Optional session ID to filter by. If None, returns all queries.
        limit: Maximum number of queries to return
        offset: Offset for pagination

    Returns:
        List of query history entries
    """
    session_manager = get_session_manager()

    if session_id:
        history = session_manager.get_session_history(session_id)
        if history is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found",
            )
        return {
            "session_id": session_id,
            "queries": [
                {
                    "question": q.question,
                    "answer": q.answer[:500] + "..."
                    if len(q.answer) > 500
                    else q.answer,
                    "sources_count": len(q.sources),
                    "timestamp": q.timestamp,
                    "latency_ms": q.latency_ms,
                }
                for q in history[offset : offset + limit]
            ],
            "total": len(history),
        }
    else:
        queries = session_manager.get_all_queries(limit=limit, offset=offset)
        return {
            "queries": [
                {
                    "question": q.question,
                    "answer": q.answer[:500] + "..."
                    if len(q.answer) > 500
                    else q.answer,
                    "sources_count": len(q.sources),
                    "timestamp": q.timestamp,
                    "latency_ms": q.latency_ms,
                }
                for q in queries
            ],
            "limit": limit,
            "offset": offset,
        }


@app.get("/export")
async def export_data(format: str = "json", session_id: Optional[str] = None):
    """Export query history in CSV or JSON format.

    Args:
        format: Export format ("json" or "csv")
        session_id: Optional session ID to export. If None, exports all queries.

    Returns:
        Exported data in requested format
    """
    session_manager = get_session_manager()

    if session_id:
        history = session_manager.get_session_history(session_id)
        if history is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found",
            )
        queries = history
    else:
        queries = session_manager.get_all_queries(limit=10000)

    if format.lower() == "csv":
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["timestamp", "question", "answer", "sources_count", "latency_ms"]
        )

        for q in queries:
            writer.writerow(
                [q.timestamp, q.question, q.answer, len(q.sources), q.latency_ms]
            )

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=query_history_{session_id or 'all'}.csv"
            },
        )
    else:
        return Response(
            content=json.dumps(
                [
                    {
                        "timestamp": q.timestamp,
                        "question": q.question,
                        "answer": q.answer,
                        "sources": q.sources,
                        "latency_ms": q.latency_ms,
                    }
                    for q in queries
                ],
                indent=2,
            ),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=query_history_{session_id or 'all'}.json"
            },
        )


@app.get("/admin/stats")
async def admin_stats(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Admin dashboard endpoint with detailed statistics.

    Requires ADMIN_API_KEY environment variable to be set.

    Args:
        x_api_key: API key from X-API-Key header

    Returns:
        Detailed admin statistics
    """
    admin_key = os.environ.get("ADMIN_API_KEY")
    if admin_key and x_api_key != admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin API key",
        )

    metrics = get_metrics_collector()
    cache = get_response_cache()
    session_manager = get_session_manager()

    return {
        "service": {
            "version": "0.2.0",
            "rag_backend": "Vertex AI"
            if _config and _config.rag.use_vertex_rag
            else "HTTP",
            "gemini_model": _config.gemini.model_name if _config else "unknown",
        },
        "metrics": metrics.get_stats(),
        "cache": cache.get_stats().__dict__,
        "sessions": session_manager.get_stats(),
        "health": await _health_checker.check_all() if _health_checker else None,
    }


@app.post("/admin/cache/clear")
async def clear_cache(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Clear response cache (admin only).

    Requires ADMIN_API_KEY environment variable to be set.
    """
    admin_key = os.environ.get("ADMIN_API_KEY")
    if admin_key and x_api_key != admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin API key",
        )

    cache = get_response_cache()
    cache.clear()

    return {"message": "Cache cleared successfully"}


@app.post("/ingest", response_model=IngestResponse)
async def trigger_ingestion(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    feed_url: Optional[str] = None,
):
    """Trigger the ingestion pipeline to discover and ingest new blog posts.

    This endpoint:
    1. Loads persisted state (tracks previously seen blog post IDs)
    2. Fetches the NVIDIA Tech Blog feed HTML
    3. Runs the full ingestion pipeline (discover → scrape → summarize → ingest)
    4. Updates and saves state

    Optional API key protection: If INGEST_API_KEY env var is set, requires
    X-API-Key header to match.

    Args:
        x_api_key: Optional API key from X-API-Key header
        feed_url: Optional custom feed URL (defaults to NVIDIA Tech Blog)

    Returns:
        IngestResponse with counts and status message

    Raises:
        HTTPException: If API key is invalid, service not initialized, or ingestion fails
    """
    # Check API key if configured
    ingest_api_key = os.environ.get("INGEST_API_KEY")
    if ingest_api_key:
        if x_api_key != ingest_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key",
            )

    if _ingest_client is None or _config is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion service not initialized",
        )

    try:
        logger.info("Starting ingestion pipeline...")

        # Load state
        state = load_state(_state_path)
        existing_ids = get_existing_ids_from_state(state)
        logger.info(f"Found {len(existing_ids)} previously seen blog post IDs")

        # Fetch feed HTML
        feed_html = await fetch_feed_html(feed_url)
        logger.info(f"Fetched {len(feed_html)} bytes of feed HTML")

        # Create dependencies
        fetcher = HttpHtmlFetcher()
        summarizer = GeminiSummarizer(_config.gemini)

        # Run ingestion pipeline
        result = await run_ingestion_pipeline(
            feed_html=feed_html,
            existing_ids=existing_ids,
            fetcher=fetcher,
            summarizer=summarizer,
            rag_client=_ingest_client,
        )

        # Update state
        update_existing_ids_in_state(state, result.new_posts)
        store_last_ingestion_result_metadata(state, result)

        # Append to history and compact
        metadata = get_last_ingestion_result_metadata(state)
        append_ingestion_history_entry(state, metadata)
        compact_ingestion_history(state, max_entries=10)

        # Save state
        save_state(state, _state_path)

        logger.info(
            f"Ingestion completed: {len(result.discovered_posts)} discovered, "
            f"{len(result.new_posts)} new, {len(result.summaries)} ingested"
        )

        return IngestResponse(
            discovered_count=len(result.discovered_posts),
            new_count=len(result.new_posts),
            ingested_count=len(result.summaries),
            message=f"Successfully processed {len(result.new_posts)} new posts",
        )

    except Exception as e:
        logger.error(f"Error during ingestion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}",
        )


# Custom exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
