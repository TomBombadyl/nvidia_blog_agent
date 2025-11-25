"""RAG retrieval tools for querying RAG backends and retrieving relevant documents.

This module provides:
- RagRetrieveClient Protocol: Abstract interface for RAG retrieval
- HttpRagRetrieveClient: Concrete HTTP client implementation

The Protocol allows easy swapping between different retrieval backends:
- Direct HTTP to CA-RAG service
- Cloud Run RAG service
- Other RAG implementations
- Test doubles for testing
"""

from typing import Protocol, List, Optional
import httpx
from nvidia_blog_agent.contracts.blog_models import RetrievedDoc
from nvidia_blog_agent.retry import retry_with_backoff


class RagRetrieveClient(Protocol):
    """Protocol for RAG retrieval clients.
    
    This abstract interface allows the system to work with various retrieval backends:
    - HTTP-based RAG services (CA-RAG, custom Cloud Run services)
    - Other RAG implementations
    - Test doubles for testing
    
    Implementations of this protocol must provide an async retrieve method.
    """
    
    async def retrieve(self, query: str, k: int = 5) -> List[RetrievedDoc]:
        """Retrieve up to k documents relevant to the query from the RAG backend.
        
        Args:
            query: The search query string.
            k: Maximum number of documents to retrieve. Defaults to 5.
        
        Returns:
            List of RetrievedDoc objects, ordered by relevance (highest score first).
        
        Raises:
            Implementation-specific exceptions (e.g., HTTP errors, network errors).
        """
        ...


def _build_query_payload(query: str, uuid: str, k: int) -> dict:
    """Build the JSON payload for RAG query.
    
    Args:
        query: The search query string.
        uuid: The corpus UUID identifier.
        k: Maximum number of documents to retrieve.
    
    Returns:
        Dictionary containing the query payload with question, uuid, and top_k fields.
    """
    return {
        "question": query,
        "uuid": uuid,
        "top_k": k,
    }


def _map_result_item(item: dict) -> Optional[RetrievedDoc]:
    """Map a single result item from RAG response to RetrievedDoc.
    
    This function handles missing or malformed fields gracefully by skipping
    entries that cannot be converted to valid RetrievedDoc objects.
    
    Args:
        item: Dictionary from RAG response results array, expected to contain:
            - page_content: str (text snippet)
            - score: float (relevance score, should be 0-1)
            - metadata: dict (containing blog_id, title, url, etc.)
    
    Returns:
        RetrievedDoc object if mapping succeeds, None if item is malformed.
    """
    try:
        # Extract required fields with defaults
        page_content = item.get("page_content", "")
        score = item.get("score", 0.0)
        metadata = item.get("metadata", {})
        
        # Validate snippet (must be non-empty)
        if not page_content or not page_content.strip():
            return None
        
        # Extract metadata fields
        blog_id = metadata.get("blog_id", "")
        title = metadata.get("title", "")
        url_str = metadata.get("url", "")
        
        # Validate URL (required for RetrievedDoc)
        if not url_str:
            return None
        
        # Clamp score to [0, 1] range
        score = max(0.0, min(1.0, float(score)))
        
        # Create RetrievedDoc
        return RetrievedDoc(
            blog_id=blog_id,
            title=title,
            url=url_str,
            snippet=page_content.strip(),
            score=score,
            metadata=metadata,
        )
    except (ValueError, TypeError, KeyError) as e:
        # Skip malformed entries
        return None


class HttpRagRetrieveClient:
    """HTTP client for retrieving documents from a RAG backend.
    
    This client queries a RAG service via HTTP POST and maps results to RetrievedDoc objects.
    It supports configurable base URL, corpus UUID, API key authentication, and timeout.
    
    Example:
        >>> client = HttpRagRetrieveClient(
        ...     base_url="https://rag.example.com",
        ...     uuid="my-corpus-id"
        ... )
        >>> docs = await client.retrieve("What is RAG?", k=5)
    """
    
    def __init__(
        self,
        base_url: str,
        uuid: str,
        *,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
    ):
        """Initialize the HTTP RAG retrieval client.
        
        Args:
            base_url: Base URL of the RAG retrieval service (e.g., CA-RAG endpoint
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
    
    async def retrieve(self, query: str, k: int = 5) -> List[RetrievedDoc]:
        """Retrieve up to k documents relevant to the query from the RAG backend.
        
        This method:
        1. Builds the query payload using _build_query_payload()
        2. POSTs to {base_url}/query
        3. Sets Content-Type: application/json
        4. Includes Authorization header if api_key is provided
        5. Maps response results to RetrievedDoc objects
        6. Skips malformed entries gracefully
        
        Args:
            query: The search query string.
            k: Maximum number of documents to retrieve. Defaults to 5.
        
        Returns:
            List of RetrievedDoc objects, ordered by relevance (highest score first).
            May be empty if no valid results are found.
        
        Raises:
            httpx.HTTPStatusError: If the HTTP response status is not 2xx.
            httpx.RequestError: If the request fails (network error, timeout, etc.).
        
        Example:
            >>> client = HttpRagRetrieveClient(
            ...     base_url="https://rag.example.com",
            ...     uuid="corpus-123"
            ... )
            >>> docs = await client.retrieve("What is RAG?", k=5)
            >>> len(docs)
            5
        """
        # Build the payload
        payload = _build_query_payload(query, self.uuid, k)
        
        # Build headers
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        # Get the HTTP client
        client = self._get_client()
        
        # Construct the endpoint URL
        url = f"{self.base_url}/query"
        
        # Make the POST request with retry logic
        async def _make_request():
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response
        
        response = await retry_with_backoff(
            _make_request,
            max_retries=3,
            initial_delay=1.0,
            max_delay=10.0,
            multiplier=2.0
        )
        
        # Parse response JSON
        response_data = response.json()
        
        # Extract results array
        results = response_data.get("results", [])
        
        # Map each result to RetrievedDoc, skipping malformed entries
        retrieved_docs = []
        for item in results:
            doc = _map_result_item(item)
            if doc is not None:
                retrieved_docs.append(doc)
        
        return retrieved_docs

