"""Vertex AI RAG Engine retrieval client.

This module provides VertexRagRetrieveClient, which queries Vertex AI RAG Engine
to retrieve relevant documents for question answering.
"""

from typing import List, Optional
from nvidia_blog_agent.contracts.blog_models import RetrievedDoc
from nvidia_blog_agent.tools.rag_retrieve import RagRetrieveClient

try:
    from google.cloud import aiplatform
    from google.cloud.aiplatform import initializer
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    aiplatform = None
    initializer = None

try:
    from google.genai import types as genai_types
    GENAI_ADK_AVAILABLE = True
except ImportError:
    GENAI_ADK_AVAILABLE = False
    genai_types = None


class VertexRagRetrieveClient(RagRetrieveClient):
    """Vertex AI RAG Engine retrieval client.
    
    This client queries Vertex AI RAG Engine to retrieve relevant documents.
    It uses the Vertex AI Python SDK to call the RAG Engine query API.
    
    Attributes:
        project_id: GCP project ID.
        location: Region where the RAG corpus is located (e.g., "us-central1").
        corpus_id: RAG corpus identifier.
        client: Optional pre-configured Vertex AI client.
    """
    
    def __init__(
        self,
        project_id: str,
        location: str,
        corpus_id: str,
        client: Optional[aiplatform.Client] = None,
    ):
        """Initialize Vertex AI RAG retrieval client.
        
        Args:
            project_id: GCP project ID.
            location: Region where the RAG corpus is located (e.g., "us-central1").
            corpus_id: RAG corpus identifier.
            client: Optional pre-configured Vertex AI client. If None, creates a new client.
        
        Raises:
            ImportError: If google-cloud-aiplatform is not installed.
        """
        if not VERTEX_AI_AVAILABLE:
            raise ImportError(
                "google-cloud-aiplatform is required for VertexRagRetrieveClient. "
                "Install it with: pip install google-cloud-aiplatform"
            )
        
        self.project_id = project_id
        self.location = location
        self.corpus_id = corpus_id
        
        if client is not None:
            self._client = client
        else:
            # Initialize Vertex AI client
            initializer.global_config.init(
                project=project_id,
                location=location,
            )
            self._client = aiplatform
    
    async def retrieve(self, query: str, k: int = 5) -> List[RetrievedDoc]:
        """Retrieve relevant documents from Vertex AI RAG Engine.
        
        Queries the RAG Engine with the given query string and returns
        up to k relevant documents as RetrievedDoc objects.
        
        Args:
            query: The search query string.
            k: Maximum number of documents to retrieve. Defaults to 5.
        
        Returns:
            List of RetrievedDoc objects, up to k items.
        
        Raises:
            Exception: If RAG Engine query fails (e.g., API errors, network errors).
        """
        # Use Vertex AI RAG Engine API
        # Note: The exact API may vary; this is a reasonable abstraction
        # that can be adapted to the actual Vertex AI RAG Engine REST API
        
        try:
            # Try using ADK if available (cleaner integration)
            if GENAI_ADK_AVAILABLE:
                return await self._retrieve_via_adk(query, k)
            else:
                # Fall back to direct REST API calls
                return await self._retrieve_via_rest(query, k)
        except Exception as e:
            # If ADK method fails, try REST fallback
            if GENAI_ADK_AVAILABLE:
                return await self._retrieve_via_rest(query, k)
            raise
    
    async def _retrieve_via_adk(self, query: str, k: int) -> List[RetrievedDoc]:
        """Retrieve using ADK's Vertex AI Search Grounding (if available)."""
        # This would use ADK's grounding tool
        # For now, fall back to REST
        return await self._retrieve_via_rest(query, k)
    
    async def _retrieve_via_rest(self, query: str, k: int) -> List[RetrievedDoc]:
        """Retrieve using Vertex AI RAG Engine REST API."""
        import httpx
        
        # Construct the RAG Engine query endpoint
        # Format: https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/ragCorpora/{corpus_id}:query
        endpoint = (
            f"https://{self.location}-aiplatform.googleapis.com/v1/"
            f"projects/{self.project_id}/locations/{self.location}/"
            f"ragCorpora/{self.corpus_id}:query"
        )
        
        # Build request payload
        payload = {
            "query": query,
            "top_k": k,
        }
        
        # Get credentials for authentication
        from google.auth import default
        from google.auth.transport.requests import Request as AuthRequest
        import asyncio
        
        credentials, _ = default()
        
        # Refresh credentials if needed (synchronous operation)
        if not credentials.valid:
            credentials.refresh(AuthRequest())
        
        # Make authenticated request
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get access token (credentials are already refreshed)
            token = credentials.token
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
        
        # Map RAG Engine response to RetrievedDoc objects
        docs: List[RetrievedDoc] = []
        
        # The response structure may vary; adapt based on actual API response
        # Expected structure: {"contexts": [{"text": "...", "source_uri": "...", "score": 0.9}]}
        contexts = result.get("contexts", [])
        
        for item in contexts[:k]:
            text = item.get("text", "")
            source_uri = item.get("source_uri", "")
            score = item.get("score", 0.0)
            
            # Extract metadata from source_uri or item metadata
            metadata = item.get("metadata", {})
            
            # Try to extract blog_id, title, url from metadata or source_uri
            blog_id = metadata.get("blog_id", "")
            title = metadata.get("title", "NVIDIA Blog Post")
            url = metadata.get("url", source_uri)
            
            docs.append(
                RetrievedDoc(
                    blog_id=blog_id or "unknown",
                    title=title,
                    url=url if url else "https://developer.nvidia.com/blog",
                    snippet=text[:500] if text else "",  # Truncate snippet
                    score=max(0.0, min(1.0, float(score))),  # Clamp to [0, 1]
                    metadata=metadata,
                )
            )
        
        return docs

