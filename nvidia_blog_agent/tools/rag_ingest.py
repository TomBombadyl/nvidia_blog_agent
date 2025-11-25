"""RAG ingestion tools for ingesting BlogSummary objects into RAG backends.

This module provides:
- RagIngestClient Protocol: Abstract interface for RAG ingestion
- HttpRagIngestClient: Concrete HTTP client implementation

The Protocol allows easy swapping between different ingestion backends:
- Direct HTTP to CA-RAG service
- Cloud Run RAG service
- GCS-based ingestion pipeline
- Test doubles for testing
"""

from typing import Protocol, Optional
import httpx
from nvidia_blog_agent.contracts.blog_models import BlogSummary
from nvidia_blog_agent.retry import retry_with_backoff


class RagIngestClient(Protocol):
    """Protocol for RAG ingestion clients.
    
    This abstract interface allows the system to work with various ingestion backends:
    - HTTP-based RAG services (CA-RAG, custom Cloud Run services)
    - GCS-based ingestion pipelines
    - Test doubles for testing
    
    Implementations of this protocol must provide an async ingest_summary method.
    """
    
    async def ingest_summary(self, summary: BlogSummary) -> None:
        """Ingest a single BlogSummary into the RAG backend.
        
        Args:
            summary: The BlogSummary object to ingest.
        
        Raises:
            Implementation-specific exceptions (e.g., HTTP errors, network errors).
        """
        ...


def _build_payload(summary: BlogSummary, uuid: str) -> dict:
    """Build the JSON payload for RAG ingestion.
    
    Args:
        summary: The BlogSummary object to ingest.
        uuid: The corpus UUID identifier.
    
    Returns:
        Dictionary containing the ingestion payload with document, doc_index,
        doc_metadata, and uuid fields.
    """
    # Build doc_metadata
    doc_metadata = {
        "blog_id": summary.blog_id,
        "title": summary.title,
        "url": str(summary.url),
        "published_at": summary.published_at.isoformat() if summary.published_at else None,
        "keywords": summary.keywords,
        "source": "nvidia_tech_blog",
        "uuid": uuid,
    }
    
    # Build the full payload
    payload = {
        "document": summary.to_rag_document(),
        "doc_index": 0,
        "doc_metadata": doc_metadata,
        "uuid": uuid,
    }
    
    return payload


class HttpRagIngestClient:
    """HTTP client for ingesting BlogSummary objects into a RAG backend.
    
    This client sends BlogSummary objects to a RAG ingestion service via HTTP POST.
    It supports configurable base URL, corpus UUID, API key authentication, and timeout.
    
    Example:
        >>> client = HttpRagIngestClient(
        ...     base_url="https://rag.example.com",
        ...     uuid="my-corpus-id"
        ... )
        >>> await client.ingest_summary(summary)
    """
    
    def __init__(
        self,
        base_url: str,
        uuid: str,
        *,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
    ):
        """Initialize the HTTP RAG ingestion client.
        
        Args:
            base_url: Base URL of the RAG ingestion service (e.g., CA-RAG endpoint
                     or Cloud Run service URL). Trailing slashes will be stripped.
            uuid: Logical corpus identifier (e.g., CA-RAG's corpus ID).
            api_key: Optional bearer token or API key for Authorization header.
            timeout: Request timeout in seconds. Defaults to 10.0.
        """
        # Normalize base_url: remove trailing slash if present
        self.base_url = base_url.rstrip("/")
        self.uuid = uuid
        self.api_key = api_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client with connection pooling.
        
        Returns:
            The httpx.AsyncClient instance with connection pooling enabled.
        """
        if self._client is None:
            # Use connection pooling with limits for better performance
            limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=limits,
                http2=True  # Enable HTTP/2 for better performance
            )
        return self._client
    
    async def ingest_summary(self, summary: BlogSummary) -> None:
        """Ingest a single BlogSummary into the RAG backend.
        
        This method:
        1. Builds the ingestion payload using _build_payload()
        2. POSTs to {base_url}/add_doc
        3. Sets Content-Type: application/json
        4. Includes Authorization header if api_key is provided
        5. Raises exceptions on non-2xx responses
        
        Args:
            summary: The BlogSummary object to ingest.
        
        Raises:
            httpx.HTTPStatusError: If the HTTP response status is not 2xx.
            httpx.RequestError: If the request fails (network error, timeout, etc.).
        
        Example:
            >>> client = HttpRagIngestClient(
            ...     base_url="https://rag.example.com",
            ...     uuid="corpus-123"
            ... )
            >>> await client.ingest_summary(summary)
        """
        # Build the payload
        payload = _build_payload(summary, self.uuid)
        
        # Build headers
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        # Get the HTTP client
        client = self._get_client()
        
        # Construct the endpoint URL
        url = f"{self.base_url}/add_doc"
        
        # Make the POST request with retry logic
        async def _make_request():
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response
        
        await retry_with_backoff(
            _make_request,
            max_retries=3,
            initial_delay=1.0,
            max_delay=10.0,
            multiplier=2.0
        )

