"""Application configuration module.

This module centralizes all runtime configuration settings, loading them
from environment variables. It provides dataclasses for structured config
and a function to load configuration from the environment.
"""

import os
from dataclasses import dataclass


@dataclass
class GeminiConfig:
    """Configuration for Gemini/LLM model access.

    Attributes:
        model_name: Name of the Gemini model to use (e.g., "gemini-1.5-pro").
        location: Optional region/endpoint for the model (e.g., "us-central1").
                  Required for some deployment scenarios, optional for others.
    """

    model_name: str
    location: str | None = None


@dataclass
class RagConfig:
    """Configuration for RAG backend service.

    Attributes:
        base_url: Base URL of the RAG service (e.g., "https://my-rag-service.run.app").
                  Required for HTTP-based RAG backends. Can be None for Vertex AI RAG.
        uuid: Corpus identifier/UUID for the RAG backend.
              For Vertex AI RAG, this is the corpus ID.
        api_key: Optional API key/bearer token for authentication.
        use_vertex_rag: Whether to use Vertex AI RAG Engine (True) or HTTP backend (False).
        vertex_location: Region for Vertex AI RAG (e.g., "us-central1"). Required if use_vertex_rag=True.
        docs_bucket: GCS bucket for storing documents (e.g., "gs://nvidia-blog-rag-docs").
                     Required if use_vertex_rag=True.
        search_engine_name: Vertex AI Search engine resource name. Optional, used for direct Search queries.
    """

    base_url: str | None = None
    uuid: str = ""
    api_key: str | None = None
    use_vertex_rag: bool = False
    vertex_location: str | None = None
    docs_bucket: str | None = None
    search_engine_name: str | None = None


@dataclass
class AppConfig:
    """Main application configuration container.

    Attributes:
        gemini: Configuration for Gemini/LLM models.
        rag: Configuration for RAG backend service.
    """

    gemini: GeminiConfig
    rag: RagConfig


def load_config_from_env() -> AppConfig:
    """Load application configuration from environment variables.

    Expected environment variables:
      GEMINI_MODEL_NAME      e.g. "gemini-1.5-pro"
      GEMINI_LOCATION        e.g. "us-central1" (optional depending on client)

      For HTTP-based RAG:
      RAG_BASE_URL           e.g. "https://my-rag-service-abc.run.app"
      RAG_UUID               corpus identifier
      RAG_API_KEY            optional bearer token for RAG service

      For Vertex AI RAG:
      USE_VERTEX_RAG         "true" to enable Vertex AI RAG Engine
      RAG_CORPUS_ID          Vertex AI RAG corpus ID (can use RAG_UUID)
      VERTEX_LOCATION        e.g. "us-central1" (required for Vertex RAG)
      RAG_DOCS_BUCKET        e.g. "gs://nvidia-blog-rag-docs" (required for Vertex RAG)
      RAG_SEARCH_ENGINE_NAME optional Vertex AI Search engine name

    Raises:
        KeyError: If required environment variables are missing based on RAG backend type.

    Returns:
        AppConfig instance with all configuration loaded from environment.

    Example:
        >>> import os
        >>> os.environ["RAG_BASE_URL"] = "https://example.com"
        >>> os.environ["RAG_UUID"] = "test-uuid"
        >>> config = load_config_from_env()
        >>> config.rag.base_url
        'https://example.com'
    """
    gemini_model = os.environ.get("GEMINI_MODEL_NAME", "gemini-1.5-pro")
    gemini_location = os.environ.get("GEMINI_LOCATION")

    # Check if using Vertex AI RAG
    use_vertex_rag = os.environ.get("USE_VERTEX_RAG", "").lower() == "true"

    if use_vertex_rag:
        # Vertex AI RAG configuration
        rag_uuid = os.environ.get("RAG_CORPUS_ID") or os.environ.get("RAG_UUID")
        vertex_location = os.environ.get("VERTEX_LOCATION")
        docs_bucket = os.environ.get("RAG_DOCS_BUCKET")

        if not rag_uuid:
            raise KeyError(
                "RAG_CORPUS_ID or RAG_UUID environment variable is required for Vertex AI RAG"
            )
        if not vertex_location:
            raise KeyError(
                "VERTEX_LOCATION environment variable is required for Vertex AI RAG"
            )
        if not docs_bucket:
            raise KeyError(
                "RAG_DOCS_BUCKET environment variable is required for Vertex AI RAG"
            )

        rag_config = RagConfig(
            base_url=None,
            uuid=rag_uuid,
            api_key=None,
            use_vertex_rag=True,
            vertex_location=vertex_location,
            docs_bucket=docs_bucket,
            search_engine_name=os.environ.get("RAG_SEARCH_ENGINE_NAME"),
        )
    else:
        # HTTP-based RAG configuration
        rag_base_url = os.environ.get("RAG_BASE_URL")
        rag_uuid = os.environ.get("RAG_UUID")

        if not rag_base_url:
            raise KeyError(
                "RAG_BASE_URL environment variable is required for HTTP-based RAG"
            )
        if not rag_uuid:
            raise KeyError(
                "RAG_UUID environment variable is required for HTTP-based RAG"
            )

        rag_config = RagConfig(
            base_url=rag_base_url,
            uuid=rag_uuid,
            api_key=os.environ.get("RAG_API_KEY"),
            use_vertex_rag=False,
        )

    return AppConfig(
        gemini=GeminiConfig(
            model_name=gemini_model,
            location=gemini_location,
        ),
        rag=rag_config,
    )
