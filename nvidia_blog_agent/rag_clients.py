"""Factory functions for creating RAG client instances.

This module provides factory functions to create configured instances of
RagIngestClient and RagRetrieveClient using application configuration.
Supports both HTTP-based RAG backends and Vertex AI RAG Engine.
"""

import os
from nvidia_blog_agent.config import AppConfig
from nvidia_blog_agent.tools.rag_ingest import HttpRagIngestClient, RagIngestClient
from nvidia_blog_agent.tools.rag_retrieve import HttpRagRetrieveClient, RagRetrieveClient


def create_rag_clients(config: AppConfig) -> tuple[RagIngestClient, RagRetrieveClient]:
    """Create configured RAG ingest and retrieve clients.
    
    This factory function creates both RAG clients based on the configuration.
    If config.rag.use_vertex_rag is True, creates Vertex AI RAG clients.
    Otherwise, creates HTTP-based clients.
    
    Args:
        config: AppConfig instance containing RAG configuration.
    
    Returns:
        Tuple of (RagIngestClient, RagRetrieveClient) instances configured
        with the provided settings.
    
    Raises:
        ValueError: If configuration is invalid for the selected RAG backend.
        ImportError: If required dependencies are missing for Vertex AI RAG.
    
    Example:
        >>> from nvidia_blog_agent.config import load_config_from_env
        >>> config = load_config_from_env()
        >>> ingest_client, retrieve_client = create_rag_clients(config)
        >>> # Use clients...
    """
    if config.rag.use_vertex_rag:
        return _create_vertex_rag_clients(config)
    else:
        return _create_http_rag_clients(config)


def _create_http_rag_clients(config: AppConfig) -> tuple[RagIngestClient, RagRetrieveClient]:
    """Create HTTP-based RAG clients."""
    if not config.rag.base_url:
        raise ValueError("RAG_BASE_URL is required for HTTP-based RAG")
    if not config.rag.uuid:
        raise ValueError("RAG_UUID is required for HTTP-based RAG")
    
    ingest = HttpRagIngestClient(
        base_url=config.rag.base_url,
        uuid=config.rag.uuid,
        api_key=config.rag.api_key,
    )
    retrieve = HttpRagRetrieveClient(
        base_url=config.rag.base_url,
        uuid=config.rag.uuid,
        api_key=config.rag.api_key,
    )
    return ingest, retrieve


def _create_vertex_rag_clients(config: AppConfig) -> tuple[RagIngestClient, RagRetrieveClient]:
    """Create Vertex AI RAG clients."""
    if not config.rag.docs_bucket:
        raise ValueError("RAG_DOCS_BUCKET is required for Vertex AI RAG")
    if not config.rag.vertex_location:
        raise ValueError("VERTEX_LOCATION is required for Vertex AI RAG")
    if not config.rag.uuid:
        raise ValueError("RAG_CORPUS_ID is required for Vertex AI RAG")
    
    # Import here to avoid import errors if dependencies aren't installed
    try:
        from nvidia_blog_agent.tools.gcs_rag_ingest import GcsRagIngestClient
        from nvidia_blog_agent.tools.vertex_rag_retrieve import VertexRagRetrieveClient
    except ImportError as e:
        raise ImportError(
            "Vertex AI RAG dependencies are required. "
            "Install with: pip install google-cloud-storage google-cloud-aiplatform"
        ) from e
    
    # Extract bucket name from gs:// URL if provided
    bucket_name = config.rag.docs_bucket
    if bucket_name.startswith("gs://"):
        bucket_name = bucket_name[5:]
    bucket_name = bucket_name.rstrip("/")
    
    # Get project ID from environment or config
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
    if not project_id:
        # Try to infer from credentials
        try:
            from google.auth import default
            credentials, project = default()
            project_id = project
        except Exception:
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT or GCP_PROJECT environment variable is required "
                "for Vertex AI RAG"
            )
    
    # Create GCS ingestion client
    ingest = GcsRagIngestClient(bucket_name=bucket_name)
    
    # Create Vertex AI retrieval client
    retrieve = VertexRagRetrieveClient(
        project_id=project_id,
        location=config.rag.vertex_location,
        corpus_id=config.rag.uuid,
    )
    
    return ingest, retrieve

