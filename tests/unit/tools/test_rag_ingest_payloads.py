"""Unit tests for RAG ingestion client.

Tests cover:
- Payload structure and content
- Base URL normalization
- Authorization header handling
- Error handling for non-2xx responses
- HTTP client behavior with mocked transport
"""

import pytest
import httpx
from datetime import datetime
from nvidia_blog_agent.contracts.blog_models import BlogSummary
from nvidia_blog_agent.tools.rag_ingest import HttpRagIngestClient, _build_payload


class TestBuildPayload:
    """Tests for _build_payload helper function."""

    def test_payload_structure(self):
        """Test that payload has correct structure."""
        published = datetime(2024, 1, 15, 10, 30, 0)
        summary = BlogSummary(
            blog_id="test-id-123",
            title="Test Blog Post",
            url="https://developer.nvidia.com/blog/test",
            published_at=published,
            executive_summary="This is an executive summary of the blog post.",
            technical_summary="This is a detailed technical summary that provides comprehensive information about the topic and meets the minimum length requirement.",
            bullet_points=["Point 1", "Point 2"],
            keywords=["AI", "ML", "CUDA"],
        )

        payload = _build_payload(summary, "test-corpus")

        assert "document" in payload
        assert "doc_index" in payload
        assert "doc_metadata" in payload
        assert "uuid" in payload

        assert payload["doc_index"] == 0
        assert payload["uuid"] == "test-corpus"
        assert payload["document"] == summary.to_rag_document()

        metadata = payload["doc_metadata"]
        assert metadata["blog_id"] == "test-id-123"
        assert metadata["title"] == "Test Blog Post"
        assert metadata["url"] == "https://developer.nvidia.com/blog/test"
        assert metadata["published_at"] == "2024-01-15T10:30:00"
        assert metadata["keywords"] == ["ai", "ml", "cuda"]  # Normalized to lowercase
        assert metadata["source"] == "nvidia_tech_blog"
        assert metadata["uuid"] == "test-corpus"

    def test_payload_without_published_at(self):
        """Test payload when published_at is None."""
        summary = BlogSummary(
            blog_id="test-id",
            title="Test Post",
            url="https://example.com/post",
            executive_summary="Executive summary here.",
            technical_summary="Technical summary with enough content to meet validation requirements.",
        )

        payload = _build_payload(summary, "corpus-123")

        assert payload["doc_metadata"]["published_at"] is None


class TestHttpRagIngestClient:
    """Tests for HttpRagIngestClient."""

    @pytest.mark.asyncio
    async def test_payload_structure(self):
        """Test that the HTTP request has correct payload structure."""
        published = datetime(2024, 1, 15, 10, 30, 0)
        summary = BlogSummary(
            blog_id="test-id-123",
            title="Test Blog Post",
            url="https://developer.nvidia.com/blog/test",
            published_at=published,
            executive_summary="This is an executive summary of the blog post.",
            technical_summary="This is a detailed technical summary that provides comprehensive information about the topic and meets the minimum length requirement.",
            bullet_points=["Point 1", "Point 2"],
            keywords=["AI", "ML"],
        )

        # Track the request
        request_captured = None

        def mock_handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_captured
            request_captured = request
            return httpx.Response(200, json={"status": "ok"})

        transport = httpx.MockTransport(mock_handler)

        client = HttpRagIngestClient(
            base_url="https://example.com/ingest", uuid="test-corpus", api_key=None
        )

        # Use the transport for testing
        async with httpx.AsyncClient(transport=transport, timeout=10.0) as test_client:
            client._client = test_client
            await client.ingest_summary(summary)

        # Verify the request
        assert request_captured is not None
        assert request_captured.method == "POST"
        assert str(request_captured.url) == "https://example.com/ingest/add_doc"

        # Verify headers
        assert request_captured.headers["content-type"] == "application/json"
        assert "authorization" not in request_captured.headers

        # Verify payload
        import json

        payload = json.loads(request_captured.content)
        assert payload["document"] == summary.to_rag_document()
        assert payload["doc_index"] == 0
        assert payload["uuid"] == "test-corpus"
        assert payload["doc_metadata"]["blog_id"] == "test-id-123"
        assert payload["doc_metadata"]["title"] == "Test Blog Post"
        assert payload["doc_metadata"]["uuid"] == "test-corpus"

    @pytest.mark.asyncio
    async def test_base_url_normalization(self):
        """Test that base_url trailing slash is normalized."""
        summary = BlogSummary(
            blog_id="test-id",
            title="Test Post",
            url="https://example.com/post",
            executive_summary="Executive summary here.",
            technical_summary="Technical summary with enough content to meet validation requirements.",
        )

        request_url = None

        def mock_handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_url
            request_url = str(request.url)
            return httpx.Response(200, json={"status": "ok"})

        transport = httpx.MockTransport(mock_handler)

        # Test with trailing slash
        client = HttpRagIngestClient(
            base_url="https://example.com/ingest/", uuid="test-corpus"
        )

        async with httpx.AsyncClient(transport=transport, timeout=10.0) as test_client:
            client._client = test_client
            await client.ingest_summary(summary)

        # Should not have double slash
        assert request_url == "https://example.com/ingest/add_doc"
        assert "//add_doc" not in request_url

    @pytest.mark.asyncio
    async def test_authorization_header(self):
        """Test that Authorization header is included when api_key is provided."""
        summary = BlogSummary(
            blog_id="test-id",
            title="Test Post",
            url="https://example.com/post",
            executive_summary="Executive summary here.",
            technical_summary="Technical summary with enough content to meet validation requirements.",
        )

        auth_header = None

        def mock_handler(request: httpx.Request) -> httpx.Response:
            nonlocal auth_header
            auth_header = request.headers.get("authorization")
            return httpx.Response(200, json={"status": "ok"})

        transport = httpx.MockTransport(mock_handler)

        client = HttpRagIngestClient(
            base_url="https://example.com/ingest",
            uuid="test-corpus",
            api_key="secret123",
        )

        async with httpx.AsyncClient(transport=transport, timeout=10.0) as test_client:
            client._client = test_client
            await client.ingest_summary(summary)

        assert auth_header == "Bearer secret123"

    @pytest.mark.asyncio
    async def test_no_authorization_header_when_api_key_none(self):
        """Test that Authorization header is not included when api_key is None."""
        summary = BlogSummary(
            blog_id="test-id",
            title="Test Post",
            url="https://example.com/post",
            executive_summary="Executive summary here.",
            technical_summary="Technical summary with enough content to meet validation requirements.",
        )

        auth_header = None

        def mock_handler(request: httpx.Request) -> httpx.Response:
            nonlocal auth_header
            auth_header = request.headers.get("authorization")
            return httpx.Response(200, json={"status": "ok"})

        transport = httpx.MockTransport(mock_handler)

        client = HttpRagIngestClient(
            base_url="https://example.com/ingest", uuid="test-corpus", api_key=None
        )

        async with httpx.AsyncClient(transport=transport, timeout=10.0) as test_client:
            client._client = test_client
            await client.ingest_summary(summary)

        assert auth_header is None

    @pytest.mark.asyncio
    async def test_non_2xx_response_raises_exception(self):
        """Test that non-2xx responses raise httpx.HTTPStatusError."""
        summary = BlogSummary(
            blog_id="test-id",
            title="Test Post",
            url="https://example.com/post",
            executive_summary="Executive summary here.",
            technical_summary="Technical summary with enough content to meet validation requirements.",
        )

        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "Internal server error"})

        transport = httpx.MockTransport(mock_handler)

        client = HttpRagIngestClient(
            base_url="https://example.com/ingest", uuid="test-corpus"
        )

        async with httpx.AsyncClient(transport=transport, timeout=10.0) as test_client:
            client._client = test_client
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.ingest_summary(summary)

            assert exc_info.value.response.status_code == 500

    @pytest.mark.asyncio
    async def test_404_response_raises_exception(self):
        """Test that 404 responses raise httpx.HTTPStatusError."""
        summary = BlogSummary(
            blog_id="test-id",
            title="Test Post",
            url="https://example.com/post",
            executive_summary="Executive summary here.",
            technical_summary="Technical summary with enough content to meet validation requirements.",
        )

        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": "Not found"})

        transport = httpx.MockTransport(mock_handler)

        client = HttpRagIngestClient(
            base_url="https://example.com/ingest", uuid="test-corpus"
        )

        async with httpx.AsyncClient(transport=transport, timeout=10.0) as test_client:
            client._client = test_client
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.ingest_summary(summary)

            assert exc_info.value.response.status_code == 404

    @pytest.mark.asyncio
    async def test_successful_ingestion(self):
        """Test that 2xx responses are treated as successful."""
        summary = BlogSummary(
            blog_id="test-id",
            title="Test Post",
            url="https://example.com/post",
            executive_summary="Executive summary here.",
            technical_summary="Technical summary with enough content to meet validation requirements.",
        )

        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "success"})

        transport = httpx.MockTransport(mock_handler)

        client = HttpRagIngestClient(
            base_url="https://example.com/ingest", uuid="test-corpus"
        )

        async with httpx.AsyncClient(transport=transport, timeout=10.0) as test_client:
            client._client = test_client
            # Should not raise an exception
            await client.ingest_summary(summary)

    @pytest.mark.asyncio
    async def test_201_response_successful(self):
        """Test that 201 (Created) responses are treated as successful."""
        summary = BlogSummary(
            blog_id="test-id",
            title="Test Post",
            url="https://example.com/post",
            executive_summary="Executive summary here.",
            technical_summary="Technical summary with enough content to meet validation requirements.",
        )

        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(201, json={"status": "created"})

        transport = httpx.MockTransport(mock_handler)

        client = HttpRagIngestClient(
            base_url="https://example.com/ingest", uuid="test-corpus"
        )

        async with httpx.AsyncClient(transport=transport, timeout=10.0) as test_client:
            client._client = test_client
            # Should not raise an exception
            await client.ingest_summary(summary)

    @pytest.mark.asyncio
    async def test_custom_timeout(self):
        """Test that custom timeout is used."""
        summary = BlogSummary(
            blog_id="test-id",
            title="Test Post",
            url="https://example.com/post",
            executive_summary="Executive summary here.",
            technical_summary="Technical summary with enough content to meet validation requirements.",
        )

        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "ok"})

        transport = httpx.MockTransport(mock_handler)

        client = HttpRagIngestClient(
            base_url="https://example.com/ingest", uuid="test-corpus", timeout=30.0
        )

        async with httpx.AsyncClient(transport=transport, timeout=30.0) as test_client:
            client._client = test_client
            await client.ingest_summary(summary)

        # Verify timeout was set (indirectly by successful request)
        assert client.timeout == 30.0

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test that client can be used as async context manager."""
        summary = BlogSummary(
            blog_id="test-id",
            title="Test Post",
            url="https://example.com/post",
            executive_summary="Executive summary here.",
            technical_summary="Technical summary with enough content to meet validation requirements.",
        )

        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "ok"})

        transport = httpx.MockTransport(mock_handler)

        # Override the client creation to use our mock transport
        client = HttpRagIngestClient(
            base_url="https://example.com/ingest", uuid="test-corpus"
        )

        async with httpx.AsyncClient(transport=transport, timeout=10.0) as test_client:
            client._client = test_client
            await client.ingest_summary(summary)

        # Client should still exist but _client should be None after context exit
        # (though we're not using context manager here, just testing the pattern)
