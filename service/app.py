"""FastAPI HTTP service for NVIDIA Blog Agent.

This service provides REST API endpoints for:
- POST /ask: Answer questions using RAG retrieval + Gemini QA
- POST /ingest: Trigger ingestion pipeline to discover and ingest new blog posts

The service is designed for Cloud Run deployment with:
- Application Default Credentials (no JSON keys in production)
- Environment-based configuration
- Proper error handling and logging
- Security best practices (optional API key protection for /ingest)
"""

import os
import logging
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global state for initialized clients (initialized at startup)
_qa_agent: Optional[QAAgent] = None
_ingest_client = None
_config = None
_state_path: Optional[str] = None


# Request/Response models
class AskRequest(BaseModel):
    """Request model for /ask endpoint."""
    question: str = Field(..., description="The question to answer", min_length=1)
    top_k: int = Field(default=5, ge=1, le=20, description="Number of documents to retrieve")


class AskResponse(BaseModel):
    """Response model for /ask endpoint."""
    answer: str = Field(..., description="The generated answer")
    sources: list[dict] = Field(..., description="List of source documents with title, url, score")


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
    global _qa_agent, _ingest_client, _config, _state_path
    
    try:
        logger.info("Initializing NVIDIA Blog Agent service...")
        
        # Load configuration from environment
        _config = load_config_from_env()
        logger.info(f"Using Gemini model: {_config.gemini.model_name}")
        logger.info(f"Using RAG backend: {'Vertex AI' if _config.rag.use_vertex_rag else 'HTTP'}")
        
        # Get state path from environment
        _state_path = os.environ.get("STATE_PATH", "state.json")
        logger.info(f"State path: {_state_path}")
        
        # Create RAG clients
        _ingest_client, retrieve_client = create_rag_clients(_config)
        
        # Create QA agent
        qa_model = GeminiQaModel(_config.gemini)
        _qa_agent = QAAgent(rag_client=retrieve_client, model=qa_model)
        
        logger.info("✅ Service initialized successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize service: {e}", exc_info=True)
        raise
    finally:
        logger.info("Shutting down service...")


# Create FastAPI app with lifespan
app = FastAPI(
    title="NVIDIA Blog Agent API",
    description="REST API for querying NVIDIA Tech Blog content using RAG",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "NVIDIA Blog Agent API",
        "status": "healthy",
        "version": "0.1.0"
    }


@app.get("/health")
async def health():
    """Health check endpoint with service status."""
    if _qa_agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not initialized"
        )
    return {
        "status": "healthy",
        "qa_agent_ready": _qa_agent is not None,
        "rag_backend": "Vertex AI" if _config and _config.rag.use_vertex_rag else "HTTP"
    }


@app.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    """Answer a question using RAG retrieval + Gemini QA.
    
    This endpoint:
    1. Retrieves relevant documents from the RAG backend
    2. Generates an answer using Gemini based on retrieved documents
    3. Returns the answer and source documents
    
    Args:
        request: AskRequest containing question and optional top_k parameter
        
    Returns:
        AskResponse with answer and source documents
        
    Raises:
        HTTPException: If service is not initialized or QA fails
    """
    if _qa_agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="QA agent not initialized"
        )
    
    try:
        logger.info(f"Processing question: {request.question[:100]}...")
        
        # Use QA agent to answer the question
        answer, retrieved_docs = await _qa_agent.answer(
            question=request.question,
            k=request.top_k
        )
        
        # Format sources
        sources = [
            {
                "title": doc.title,
                "url": str(doc.url),
                "score": doc.score,
                "snippet": doc.snippet[:200] + "..." if len(doc.snippet) > 200 else doc.snippet
            }
            for doc in retrieved_docs
        ]
        
        logger.info(f"Answer generated, {len(sources)} sources retrieved")
        
        return AskResponse(
            answer=answer,
            sources=sources
        )
        
    except Exception as e:
        logger.error(f"Error processing question: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process question: {str(e)}"
        )


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
                detail="Invalid or missing API key"
            )
    
    if _ingest_client is None or _config is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion service not initialized"
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
            message=f"Successfully processed {len(result.new_posts)} new posts"
        )
        
    except Exception as e:
        logger.error(f"Error during ingestion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}"
        )


# Custom exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )

