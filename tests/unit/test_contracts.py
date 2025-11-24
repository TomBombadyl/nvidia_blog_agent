"""Unit tests for contract models.

Tests cover:
- Model instantiation with valid data
- Required vs optional field validation
- JSON serialization/deserialization
- Field validators and constraints
- Utility functions
"""

import pytest
from datetime import datetime
from pydantic import ValidationError
from nvidia_blog_agent.contracts.blog_models import (
    BlogPost,
    RawBlogContent,
    BlogSummary,
    RetrievedDoc,
    generate_post_id,
    blog_summary_to_dict,
)


class TestBlogPost:
    """Tests for BlogPost model."""

    def test_create_minimal_blog_post(self):
        """Test creating a BlogPost with only required fields."""
        post = BlogPost(
            id="test-id-123",
            url="https://developer.nvidia.com/blog/test-post",
            title="Test Blog Post"
        )
        assert post.id == "test-id-123"
        assert str(post.url) == "https://developer.nvidia.com/blog/test-post"
        assert post.title == "Test Blog Post"
        assert post.published_at is None
        assert post.tags == []
        assert post.source == "nvidia_tech_blog"

    def test_create_full_blog_post(self):
        """Test creating a BlogPost with all fields."""
        published = datetime(2024, 1, 15, 10, 30, 0)
        post = BlogPost(
            id="test-id-456",
            url="https://developer.nvidia.com/blog/full-post",
            title="Full Blog Post",
            published_at=published,
            tags=["AI", "CUDA", "Deep Learning"],
            source="nvidia_tech_blog"
        )
        assert post.published_at == published
        assert post.tags == ["AI", "CUDA", "Deep Learning"]
        assert post.source == "nvidia_tech_blog"

    def test_blog_post_id_validation(self):
        """Test that empty ID raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BlogPost(
                id="",
                url="https://developer.nvidia.com/blog/test",
                title="Test"
            )
        assert "ID cannot be empty" in str(exc_info.value)

    def test_blog_post_json_serialization(self):
        """Test JSON serialization of BlogPost."""
        published = datetime(2024, 1, 15, 10, 30, 0)
        post = BlogPost(
            id="test-id",
            url="https://developer.nvidia.com/blog/test",
            title="Test Post",
            published_at=published,
            tags=["AI"]
        )
        
        # model_dump() with custom serializer returns ISO format for datetime
        json_dict = post.model_dump()
        assert json_dict["id"] == "test-id"
        assert json_dict["title"] == "Test Post"
        assert json_dict["published_at"] == published.isoformat()  # Serialized to ISO string
        assert json_dict["tags"] == ["AI"]
        
        # model_dump(mode='json') also serializes to JSON-compatible types
        json_serialized = post.model_dump(mode='json')
        assert json_serialized["published_at"] == published.isoformat()
        
        # Test JSON string serialization
        json_str = post.model_dump_json()
        assert "test-id" in json_str
        assert "Test Post" in json_str
        assert "2024-01-15T10:30:00" in json_str

    def test_blog_post_json_deserialization(self):
        """Test JSON deserialization of BlogPost."""
        json_data = {
            "id": "test-id",
            "url": "https://developer.nvidia.com/blog/test",
            "title": "Test Post",
            "published_at": "2024-01-15T10:30:00",
            "tags": ["AI", "ML"]
        }
        post = BlogPost.model_validate(json_data)
        assert post.id == "test-id"
        assert post.title == "Test Post"
        assert post.published_at == datetime(2024, 1, 15, 10, 30, 0)
        assert post.tags == ["AI", "ML"]


class TestRawBlogContent:
    """Tests for RawBlogContent model."""

    def test_create_raw_blog_content(self):
        """Test creating RawBlogContent with all fields."""
        content = RawBlogContent(
            blog_id="test-id-123",
            url="https://developer.nvidia.com/blog/test",
            title="Test Post",
            html="<html><body><h1>Test</h1><p>Content</p></body></html>",
            text="Test\n\nContent",
            sections=["Introduction", "Main Content", "Conclusion"]
        )
        assert content.blog_id == "test-id-123"
        assert content.title == "Test Post"
        assert len(content.html) > 0
        assert len(content.text) > 0
        assert len(content.sections) == 3

    def test_raw_blog_content_minimal(self):
        """Test creating RawBlogContent with minimal required fields."""
        content = RawBlogContent(
            blog_id="test-id",
            url="https://developer.nvidia.com/blog/test",
            title="Test",
            html="<html>Test</html>",
            text="Test"
        )
        assert content.sections == []

    def test_raw_blog_content_validation(self):
        """Test that empty required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            RawBlogContent(
                blog_id="",
                url="https://developer.nvidia.com/blog/test",
                title="Test",
                html="<html>Test</html>",
                text="Test"
            )
        
        with pytest.raises(ValidationError):
            RawBlogContent(
                blog_id="test-id",
                url="https://developer.nvidia.com/blog/test",
                title="",
                html="<html>Test</html>",
                text="Test"
            )

    def test_raw_blog_content_json_serialization(self):
        """Test JSON serialization of RawBlogContent."""
        content = RawBlogContent(
            blog_id="test-id",
            url="https://developer.nvidia.com/blog/test",
            title="Test Post",
            html="<html>Test</html>",
            text="Test",
            sections=["Section 1", "Section 2"]
        )
        
        json_dict = content.model_dump()
        assert json_dict["blog_id"] == "test-id"
        assert json_dict["title"] == "Test Post"
        assert json_dict["sections"] == ["Section 1", "Section 2"]


class TestBlogSummary:
    """Tests for BlogSummary model."""

    def test_create_blog_summary(self):
        """Test creating BlogSummary with all fields."""
        published = datetime(2024, 1, 15, 10, 30, 0)
        summary = BlogSummary(
            blog_id="test-id-123",
            title="Test Blog Post",
            url="https://developer.nvidia.com/blog/test",
            published_at=published,
            executive_summary="This is a high-level summary of the blog post.",
            technical_summary="This is a detailed technical summary that explains the concepts, methodologies, and implementation details discussed in the blog post.",
            bullet_points=[
                "Key point 1",
                "Key point 2",
                "Key point 3"
            ],
            keywords=["AI", "CUDA", "Deep Learning", "NVIDIA"]
        )
        assert summary.blog_id == "test-id-123"
        assert summary.executive_summary.startswith("This is")
        assert len(summary.technical_summary) >= 50
        assert len(summary.bullet_points) == 3
        assert len(summary.keywords) == 4

    def test_blog_summary_minimal(self):
        """Test creating BlogSummary with minimal required fields."""
        summary = BlogSummary(
            blog_id="test-id",
            title="Test",
            url="https://developer.nvidia.com/blog/test",
            executive_summary="Short summary.",
            technical_summary="This is a detailed technical summary that provides comprehensive information about the topic."
        )
        assert summary.bullet_points == []
        assert summary.keywords == []
        assert summary.published_at is None

    def test_blog_summary_keyword_normalization(self):
        """Test that keywords are normalized to lowercase and deduplicated."""
        summary = BlogSummary(
            blog_id="test-id",
            title="Test",
            url="https://developer.nvidia.com/blog/test",
            executive_summary="This is a valid executive summary that meets the minimum length requirement.",
            technical_summary="Detailed technical summary with enough content to pass validation and meet the minimum character requirement.",
            keywords=["AI", "ai", "CUDA", "cuda", "Deep Learning", "  deep learning  "]
        )
        # Should be deduplicated and normalized
        assert "ai" in summary.keywords
        assert "cuda" in summary.keywords
        assert "deep learning" in summary.keywords
        assert len(summary.keywords) == 3  # Deduplicated
        assert summary.keywords.count("ai") == 1

    def test_blog_summary_to_rag_document(self):
        """Test conversion to RAG document string."""
        published = datetime(2024, 1, 15, 10, 30, 0)
        summary = BlogSummary(
            blog_id="test-id",
            title="Test Blog",
            url="https://developer.nvidia.com/blog/test",
            published_at=published,
            executive_summary="Executive summary here with enough content.",
            technical_summary="Technical details here with comprehensive information about the topic and implementation details that meet the minimum length requirement.",
            bullet_points=["Point 1", "Point 2"],
            keywords=["AI", "ML"]
        )
        
        doc = summary.to_rag_document()
        assert "Title: Test Blog" in doc
        assert "Executive Summary:" in doc
        assert "Technical Summary:" in doc
        assert "Executive summary here" in doc
        assert "Point 1" in doc
        assert "Keywords:" in doc
        assert "ai" in doc.lower()  # Keywords are normalized to lowercase
        assert "ml" in doc.lower()
        assert "2024-01-15" in doc  # Published date

    def test_blog_summary_validation(self):
        """Test that short summaries raise ValidationError."""
        with pytest.raises(ValidationError):
            BlogSummary(
                blog_id="test-id",
                title="Test",
                url="https://developer.nvidia.com/blog/test",
                executive_summary="Short",  # Too short
                technical_summary="Detailed technical summary with enough content."
            )
        
        with pytest.raises(ValidationError):
            BlogSummary(
                blog_id="test-id",
                title="Test",
                url="https://developer.nvidia.com/blog/test",
                executive_summary="This is a valid executive summary.",
                technical_summary="Short"  # Too short
            )

    def test_blog_summary_json_serialization(self):
        """Test JSON serialization of BlogSummary."""
        summary = BlogSummary(
            blog_id="test-id",
            title="Test",
            url="https://developer.nvidia.com/blog/test",
            executive_summary="Executive summary.",
            technical_summary="Detailed technical summary with comprehensive information."
        )
        
        json_dict = summary.model_dump()
        assert json_dict["blog_id"] == "test-id"
        assert json_dict["executive_summary"] == "Executive summary."
        
        json_str = summary.model_dump_json()
        assert "test-id" in json_str


class TestRetrievedDoc:
    """Tests for RetrievedDoc model."""

    def test_create_retrieved_doc(self):
        """Test creating RetrievedDoc with all fields."""
        doc = RetrievedDoc(
            blog_id="test-id-123",
            title="Test Blog Post",
            url="https://developer.nvidia.com/blog/test",
            snippet="This is a relevant snippet from the document.",
            score=0.85,
            metadata={"source": "rag", "rank": 1}
        )
        assert doc.blog_id == "test-id-123"
        assert doc.title == "Test Blog Post"
        assert doc.snippet.startswith("This is")
        assert doc.score == 0.85
        assert doc.metadata["source"] == "rag"

    def test_retrieved_doc_minimal(self):
        """Test creating RetrievedDoc with minimal required fields."""
        doc = RetrievedDoc(
            blog_id="test-id",
            title="Test",
            url="https://developer.nvidia.com/blog/test",
            snippet="Snippet",
            score=0.5
        )
        assert doc.metadata == {}

    def test_retrieved_doc_score_validation(self):
        """Test that score must be between 0.0 and 1.0."""
        # Valid scores
        RetrievedDoc(
            blog_id="test-id",
            title="Test",
            url="https://developer.nvidia.com/blog/test",
            snippet="Test",
            score=0.0
        )
        RetrievedDoc(
            blog_id="test-id",
            title="Test",
            url="https://developer.nvidia.com/blog/test",
            snippet="Test",
            score=1.0
        )
        
        # Invalid scores
        with pytest.raises(ValidationError):
            RetrievedDoc(
                blog_id="test-id",
                title="Test",
                url="https://developer.nvidia.com/blog/test",
                snippet="Test",
                score=-0.1
            )
        
        with pytest.raises(ValidationError):
            RetrievedDoc(
                blog_id="test-id",
                title="Test",
                url="https://developer.nvidia.com/blog/test",
                snippet="Test",
                score=1.1
            )

    def test_retrieved_doc_json_serialization(self):
        """Test JSON serialization of RetrievedDoc."""
        doc = RetrievedDoc(
            blog_id="test-id",
            title="Test",
            url="https://developer.nvidia.com/blog/test",
            snippet="Snippet text",
            score=0.75,
            metadata={"key": "value"}
        )
        
        json_dict = doc.model_dump()
        assert json_dict["blog_id"] == "test-id"
        assert json_dict["score"] == 0.75
        assert json_dict["metadata"]["key"] == "value"


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_generate_post_id_deterministic(self):
        """Test that generate_post_id produces deterministic results."""
        url = "https://developer.nvidia.com/blog/test-post"
        id1 = generate_post_id(url)
        id2 = generate_post_id(url)
        assert id1 == id2
        assert len(id1) == 64  # SHA256 hex string length

    def test_generate_post_id_different_urls(self):
        """Test that different URLs produce different IDs."""
        id1 = generate_post_id("https://developer.nvidia.com/blog/post1")
        id2 = generate_post_id("https://developer.nvidia.com/blog/post2")
        assert id1 != id2

    def test_blog_summary_to_dict(self):
        """Test conversion of BlogSummary to RAG ingestion dictionary."""
        published = datetime(2024, 1, 15, 10, 30, 0)
        summary = BlogSummary(
            blog_id="test-id-123",
            title="Test Blog",
            url="https://developer.nvidia.com/blog/test",
            published_at=published,
            executive_summary="Executive summary with sufficient detail.",
            technical_summary="Technical summary with comprehensive detail and enough content to meet validation requirements for the technical summary field.",
            keywords=["AI", "ML"]
        )
        
        rag_dict = blog_summary_to_dict(summary)
        assert "document" in rag_dict
        assert rag_dict["doc_index"] == "test-id-123"
        assert "doc_metadata" in rag_dict
        assert rag_dict["doc_metadata"]["blog_id"] == "test-id-123"
        assert rag_dict["doc_metadata"]["title"] == "Test Blog"
        # Keywords are normalized to lowercase by the validator
        assert rag_dict["doc_metadata"]["keywords"] == ["ai", "ml"]
        assert "Title: Test Blog" in rag_dict["document"]
        assert "Executive summary" in rag_dict["document"]

