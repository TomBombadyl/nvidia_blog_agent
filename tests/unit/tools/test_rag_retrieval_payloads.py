"""Unit tests for RAG retrieval client.

Tests cover:
- Payload structure and URL
- Authorization header handling
- Mapping results into RetrievedDoc objects
- Handling malformed entries gracefully
- Error handling for non-2xx responses
- Base URL normalization
"""

import pytest
import httpx
from datetime import datetime
from nvidia_blog_agent.contracts.blog_models import RetrievedDoc
from nvidia_blog_agent.tools.rag_retrieve import (
    HttpRagRetrieveClient,
    _build_query_payload,
    _map_result_item,
)


class TestBuildQueryPayload:
    """Tests for _build_query_payload helper function."""
    
    def test_payload_structure(self):
        """Test that payload has correct structure."""
        payload = _build_query_payload("What is RAG?", "test-corpus", k=5)
        
        assert payload["question"] == "What is RAG?"
        assert payload["uuid"] == "test-corpus"
        assert payload["top_k"] == 5
    
    def test_custom_k_value(self):
        """Test that custom k value is used."""
        payload = _build_query_payload("test query", "corpus-123", k=10)
        
        assert payload["top_k"] == 10


class TestMapResultItem:
    """Tests for _map_result_item helper function."""
    
    def test_valid_item_mapping(self):
        """Test mapping a valid result item."""
        item = {
            "page_content": "This is a relevant snippet about RAG.",
            "score": 0.87,
            "metadata": {
                "blog_id": "test-id-123",
                "title": "Test Blog Post",
                "url": "https://developer.nvidia.com/blog/test",
                "published_at": "2024-01-15T10:30:00Z",
                "keywords": ["rag", "nvidia"],
                "source": "nvidia_tech_blog",
            }
        }
        
        doc = _map_result_item(item)
        
        assert doc is not None
        assert isinstance(doc, RetrievedDoc)
        assert doc.blog_id == "test-id-123"
        assert doc.title == "Test Blog Post"
        assert str(doc.url) == "https://developer.nvidia.com/blog/test"
        assert doc.snippet == "This is a relevant snippet about RAG."
        assert doc.score == 0.87
        assert doc.metadata["keywords"] == ["rag", "nvidia"]
    
    def test_missing_url_returns_none(self):
        """Test that item without URL is skipped."""
        item = {
            "page_content": "Some content",
            "score": 0.5,
            "metadata": {
                "blog_id": "test-id",
                "title": "Test",
                # Missing url
            }
        }
        
        doc = _map_result_item(item)
        assert doc is None
    
    def test_empty_page_content_returns_none(self):
        """Test that item with empty page_content is skipped."""
        item = {
            "page_content": "",
            "score": 0.5,
            "metadata": {
                "blog_id": "test-id",
                "title": "Test",
                "url": "https://example.com/post",
            }
        }
        
        doc = _map_result_item(item)
        assert doc is None
    
    def test_score_clamping(self):
        """Test that scores are clamped to [0, 1] range."""
        # Score > 1
        item_high = {
            "page_content": "Content",
            "score": 1.5,
            "metadata": {
                "blog_id": "test-id",
                "title": "Test",
                "url": "https://example.com/post",
            }
        }
        doc_high = _map_result_item(item_high)
        assert doc_high is not None
        assert doc_high.score == 1.0
        
        # Score < 0
        item_low = {
            "page_content": "Content",
            "score": -0.5,
            "metadata": {
                "blog_id": "test-id",
                "title": "Test",
                "url": "https://example.com/post",
            }
        }
        doc_low = _map_result_item(item_low)
        assert doc_low is not None
        assert doc_low.score == 0.0
    
    def test_missing_metadata_fields(self):
        """Test that missing metadata fields use defaults."""
        item = {
            "page_content": "Content here",
            "score": 0.7,
            "metadata": {
                "url": "https://example.com/post",
                # Missing blog_id, title - should use empty strings
            }
        }
        
        doc = _map_result_item(item)
        assert doc is not None
        assert doc.blog_id == ""
        assert doc.title == ""
        assert doc.snippet == "Content here"


class TestHttpRagRetrieveClient:
    """Tests for HttpRagRetrieveClient."""
    
    @pytest.mark.asyncio
    async def test_payload_structure_and_url(self):
        """Test that the HTTP request has correct payload structure and URL."""
        request_captured = None
        
        def mock_handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_captured
            request_captured = request
            return httpx.Response(200, json={"results": []})
        
        transport = httpx.MockTransport(mock_handler)
        
        client = HttpRagRetrieveClient(
            base_url="https://example.com/rag",
            uuid="test-corpus",
            api_key=None
        )
        
        async with httpx.AsyncClient(transport=transport, timeout=10.0) as test_client:
            client._client = test_client
            await client.retrieve("What is RAG?", k=5)
        
        # Verify the request
        assert request_captured is not None
        assert request_captured.method == "POST"
        assert str(request_captured.url) == "https://example.com/rag/query"
        
        # Verify headers
        assert request_captured.headers["content-type"] == "application/json"
        assert "authorization" not in request_captured.headers
        
        # Verify payload
        import json
        payload = json.loads(request_captured.content)
        assert payload["question"] == "What is RAG?"
        assert payload["uuid"] == "test-corpus"
        assert payload["top_k"] == 5
    
    @pytest.mark.asyncio
    async def test_authorization_header(self):
        """Test that Authorization header is included when api_key is provided."""
        auth_header = None
        
        def mock_handler(request: httpx.Request) -> httpx.Response:
            nonlocal auth_header
            auth_header = request.headers.get("authorization")
            return httpx.Response(200, json={"results": []})
        
        transport = httpx.MockTransport(mock_handler)
        
        client = HttpRagRetrieveClient(
            base_url="https://example.com/rag",
            uuid="test-corpus",
            api_key="secret123"
        )
        
        async with httpx.AsyncClient(transport=transport, timeout=10.0) as test_client:
            client._client = test_client
            await client.retrieve("test query")
        
        assert auth_header == "Bearer secret123"
    
    @pytest.mark.asyncio
    async def test_mapping_results_into_retrieved_doc(self):
        """Test that response results are correctly mapped to RetrievedDoc objects."""
        response_data = {
            "results": [
                {
                    "page_content": "First snippet about RAG.",
                    "score": 0.95,
                    "metadata": {
                        "blog_id": "id-1",
                        "title": "Blog Post 1",
                        "url": "https://example.com/post1",
                        "published_at": "2024-01-15T10:30:00Z",
                        "keywords": ["rag"],
                        "source": "nvidia_tech_blog",
                    }
                },
                {
                    "page_content": "Second snippet about CUDA.",
                    "score": 0.82,
                    "metadata": {
                        "blog_id": "id-2",
                        "title": "Blog Post 2",
                        "url": "https://example.com/post2",
                        "keywords": ["cuda"],
                        "source": "nvidia_tech_blog",
                    }
                },
            ]
        }
        
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=response_data)
        
        transport = httpx.MockTransport(mock_handler)
        
        client = HttpRagRetrieveClient(
            base_url="https://example.com/rag",
            uuid="test-corpus"
        )
        
        async with httpx.AsyncClient(transport=transport, timeout=10.0) as test_client:
            client._client = test_client
            docs = await client.retrieve("test query")
        
        assert len(docs) == 2
        assert docs[0].blog_id == "id-1"
        assert docs[0].title == "Blog Post 1"
        assert docs[0].snippet == "First snippet about RAG."
        assert docs[0].score == 0.95
        assert docs[1].blog_id == "id-2"
        assert docs[1].title == "Blog Post 2"
        assert docs[1].snippet == "Second snippet about CUDA."
        assert docs[1].score == 0.82
    
    @pytest.mark.asyncio
    async def test_malformed_entries_skipped(self):
        """Test that malformed entries are skipped gracefully."""
        response_data = {
            "results": [
                {
                    # Valid entry
                    "page_content": "Valid content",
                    "score": 0.8,
                    "metadata": {
                        "blog_id": "valid-id",
                        "title": "Valid Post",
                        "url": "https://example.com/valid",
                    }
                },
                {
                    # Missing URL - should be skipped
                    "page_content": "Invalid content",
                    "score": 0.5,
                    "metadata": {
                        "blog_id": "invalid-id",
                        "title": "Invalid Post",
                        # Missing url
                    }
                },
                {
                    # Empty page_content - should be skipped
                    "page_content": "",
                    "score": 0.3,
                    "metadata": {
                        "blog_id": "empty-id",
                        "title": "Empty Post",
                        "url": "https://example.com/empty",
                    }
                },
                {
                    # Another valid entry
                    "page_content": "Another valid content",
                    "score": 0.7,
                    "metadata": {
                        "blog_id": "valid-id-2",
                        "title": "Valid Post 2",
                        "url": "https://example.com/valid2",
                    }
                },
            ]
        }
        
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=response_data)
        
        transport = httpx.MockTransport(mock_handler)
        
        client = HttpRagRetrieveClient(
            base_url="https://example.com/rag",
            uuid="test-corpus"
        )
        
        async with httpx.AsyncClient(transport=transport, timeout=10.0) as test_client:
            client._client = test_client
            docs = await client.retrieve("test query")
        
        # Should only return the 2 valid entries
        assert len(docs) == 2
        assert docs[0].blog_id == "valid-id"
        assert docs[1].blog_id == "valid-id-2"
    
    @pytest.mark.asyncio
    async def test_non_2xx_response_raises_exception(self):
        """Test that non-2xx responses raise httpx.HTTPStatusError."""
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "Internal server error"})
        
        transport = httpx.MockTransport(mock_handler)
        
        client = HttpRagRetrieveClient(
            base_url="https://example.com/rag",
            uuid="test-corpus"
        )
        
        async with httpx.AsyncClient(transport=transport, timeout=10.0) as test_client:
            client._client = test_client
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.retrieve("test query")
            
            assert exc_info.value.response.status_code == 500
    
    @pytest.mark.asyncio
    async def test_base_url_normalization(self):
        """Test that base_url trailing slash is normalized."""
        request_url = None
        
        def mock_handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_url
            request_url = str(request.url)
            return httpx.Response(200, json={"results": []})
        
        transport = httpx.MockTransport(mock_handler)
        
        # Test with trailing slash
        client = HttpRagRetrieveClient(
            base_url="https://example.com/rag/",
            uuid="test-corpus"
        )
        
        async with httpx.AsyncClient(transport=transport, timeout=10.0) as test_client:
            client._client = test_client
            await client.retrieve("test query")
        
        # Should not have double slash
        assert request_url == "https://example.com/rag/query"
        assert "//query" not in request_url
    
    @pytest.mark.asyncio
    async def test_empty_results(self):
        """Test that empty results list is handled correctly."""
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"results": []})
        
        transport = httpx.MockTransport(mock_handler)
        
        client = HttpRagRetrieveClient(
            base_url="https://example.com/rag",
            uuid="test-corpus"
        )
        
        async with httpx.AsyncClient(transport=transport, timeout=10.0) as test_client:
            client._client = test_client
            docs = await client.retrieve("test query")
        
        assert docs == []
    
    @pytest.mark.asyncio
    async def test_custom_k_value(self):
        """Test that custom k value is passed correctly."""
        request_captured = None
        
        def mock_handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_captured
            request_captured = request
            return httpx.Response(200, json={"results": []})
        
        transport = httpx.MockTransport(mock_handler)
        
        client = HttpRagRetrieveClient(
            base_url="https://example.com/rag",
            uuid="test-corpus"
        )
        
        async with httpx.AsyncClient(transport=transport, timeout=10.0) as test_client:
            client._client = test_client
            await client.retrieve("test query", k=10)
        
        import json
        payload = json.loads(request_captured.content)
        assert payload["top_k"] == 10

