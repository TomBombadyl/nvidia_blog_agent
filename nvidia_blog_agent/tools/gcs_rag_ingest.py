"""GCS-based RAG ingestion for Vertex AI RAG Engine.

This module provides GcsRagIngestClient, which writes BlogSummary objects
to Google Cloud Storage. Vertex AI Search/RAG Engine then ingests from that bucket.
"""

from typing import Optional
from nvidia_blog_agent.contracts.blog_models import BlogSummary
from nvidia_blog_agent.tools.rag_ingest import RagIngestClient

try:
    from google.cloud import storage

    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    storage = None


class GcsRagIngestClient(RagIngestClient):
    """GCS-based RAG ingestion client for Vertex AI RAG Engine.

    This client writes BlogSummary documents to Google Cloud Storage in a format
    that Vertex AI Search can ingest. The bucket should be configured as a data
    source for Vertex AI Search, which will then be used by Vertex AI RAG Engine.

    Attributes:
        bucket_name: Name of the GCS bucket (without gs:// prefix).
        prefix: Optional prefix/path within the bucket (e.g., "docs/").
        client: Optional pre-configured Storage client.
    """

    def __init__(
        self,
        bucket_name: str,
        prefix: str = "",
        client: Optional[storage.Client] = None,
    ):
        """Initialize GCS RAG ingestion client.

        Args:
            bucket_name: Name of the GCS bucket (without gs:// prefix).
            prefix: Optional prefix/path within the bucket (e.g., "docs/").
                   Documents will be written to {prefix}{blog_id}.txt
            client: Optional pre-configured Storage client. If None, creates a new client
                   using default credentials.

        Raises:
            ImportError: If google-cloud-storage is not installed.
        """
        if not GCS_AVAILABLE:
            raise ImportError(
                "google-cloud-storage is required for GcsRagIngestClient. "
                "Install it with: pip install google-cloud-storage"
            )

        self.bucket_name = bucket_name
        self.prefix = prefix.rstrip("/") + "/" if prefix else ""
        self._client = client or storage.Client()

    async def ingest_summary(self, summary: BlogSummary) -> None:
        """Ingest a BlogSummary by writing it to GCS.

        Writes the summary as a text file to:
        gs://{bucket_name}/{prefix}{blog_id}.txt

        The content is generated using summary.to_rag_document().

        Args:
            summary: The BlogSummary object to ingest.

        Raises:
            Exception: If GCS write fails (e.g., permissions, network errors).
        """
        # Generate document content
        document_content = summary.to_rag_document()

        # Construct object name
        object_name = f"{self.prefix}{summary.blog_id}.txt"

        # Write to GCS (synchronous operation, but we're in an async context)
        # In production, you might want to use async GCS client or run_in_executor
        bucket = self._client.bucket(self.bucket_name)
        blob = bucket.blob(object_name)

        # Set content type
        blob.content_type = "text/plain"

        # Upload content
        blob.upload_from_string(document_content, content_type="text/plain")

        # Optionally, also write metadata as JSON
        # This can be useful for Vertex AI Search to extract metadata
        metadata_blob_name = f"{self.prefix}{summary.blog_id}.metadata.json"
        metadata_blob = bucket.blob(metadata_blob_name)

        import json

        metadata = {
            "blog_id": summary.blog_id,
            "title": summary.title,
            "url": str(summary.url),
            "published_at": summary.published_at.isoformat()
            if summary.published_at
            else None,
            "keywords": summary.keywords,
            "source": summary.source,
            "content_type": summary.content_type,
        }
        metadata_blob.upload_from_string(
            json.dumps(metadata, indent=2), content_type="application/json"
        )
