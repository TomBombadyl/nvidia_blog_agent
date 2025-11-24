"""Vertex AI RAG Engine retrieval client.

This module provides VertexRagRetrieveClient, which queries Vertex AI RAG Engine
to retrieve relevant documents for question answering.
"""

from typing import List, Optional, Any
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
        client: Optional[Any] = None,
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
        
        # Construct the RAG Engine retrieveContexts endpoint
        # Format: https://{location}-aiplatform.googleapis.com/v1beta1/projects/{project}/locations/{location}:retrieveContexts
        endpoint = (
            f"https://{self.location}-aiplatform.googleapis.com/v1beta1/"
            f"projects/{self.project_id}/locations/{self.location}:retrieveContexts"
        )
        
        # Build corpus resource name
        corpus_resource = (
            f"projects/{self.project_id}/locations/{self.location}/"
            f"ragCorpora/{self.corpus_id}"
        )
        
        # Build request payload according to Vertex AI RAG API spec
        payload = {
            "vertex_rag_store": {
                "rag_resources": {
                    "rag_corpus": corpus_resource
                }
            },
            "query": {
                "text": query,
                "similarity_top_k": k
            }
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
        
        # The response structure from retrieveContexts API
        # Actual structure: {"contexts": {"contexts": [{"text": "...", "sourceUri": "...", "distance": 0.9}]}}
        # Note: API uses camelCase (sourceUri, distance) not snake_case
        contexts_obj = result.get("contexts", {})
        
        # Handle nested structure: contexts can be a dict with "contexts" key, or directly a list
        if isinstance(contexts_obj, dict):
            contexts = contexts_obj.get("contexts", [])
        elif isinstance(contexts_obj, list):
            contexts = contexts_obj
        else:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Unexpected response format: contexts is {type(contexts_obj)}. Response: {result}")
            return docs
        
        # Ensure contexts is a list
        if not isinstance(contexts, list):
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Unexpected response format: contexts is {type(contexts)}, not a list. Response: {result}")
            return docs
        
        # Debug: log response structure if no contexts found
        if not contexts:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"No contexts returned from RAG API. Response keys: {list(result.keys())}")
            logger.debug(f"Full response: {result}")
        
        # Limit to k documents
        contexts_to_process = contexts[:k] if len(contexts) > k else contexts
        
        for item in contexts_to_process:
            # API uses camelCase: sourceUri, distance (not source_uri, score)
            text = item.get("text", "")
            source_uri = item.get("sourceUri", item.get("source_uri", ""))
            # Distance is lower = better, so convert to score (higher = better)
            distance = item.get("distance", 1.0)
            score = max(0.0, min(1.0, 1.0 - distance)) if distance else 0.0
            
            # Extract metadata from source_uri or item metadata
            metadata = item.get("metadata", {})
            
            # Extract blog_id, title, url from text content or metadata
            # The text content has format: "Title: ...\nURL: https://...\n\nExecutive Summary:..."
            import re
            blog_id = metadata.get("blog_id", "")
            title = metadata.get("title", "NVIDIA Blog Post")
            url = metadata.get("url", "")
            
            # If URL not in metadata, extract from text content
            if not url or url.startswith("gs://"):
                # Look for "URL: https://..." pattern in text
                url_match = re.search(r'URL:\s*(https?://[^\s\n]+)', text)
                if url_match:
                    url = url_match.group(1)
                else:
                    # Fallback to default blog URL
                    url = "https://developer.nvidia.com/blog"
            
            # Extract title from text if not in metadata
            if title == "NVIDIA Blog Post":
                title_match = re.search(r'Title:\s*([^\n]+)', text)
                if title_match:
                    title = title_match.group(1).strip()
            
            # Extract blog_id from source_uri filename if not in metadata
            if not blog_id and source_uri:
                # source_uri is like: gs://bucket/blog_id.txt
                import os
                filename = os.path.basename(source_uri)
                if filename.endswith('.txt'):
                    blog_id = filename[:-4]  # Remove .txt extension
            
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

