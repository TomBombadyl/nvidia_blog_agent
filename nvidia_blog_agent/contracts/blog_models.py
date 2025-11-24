"""Core data models for NVIDIA Blog Agent.

These Pydantic models define the contracts for blog discovery, processing,
and retrieval throughout the system. They are designed to be:
- Serializable for Google Cloud services
- Compatible with MCP tool interfaces
- Flexible for various serving scenarios
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, HttpUrl, Field, field_validator, ConfigDict, model_serializer
import hashlib


class BlogPost(BaseModel):
    """Represents a discovered NVIDIA tech blog post.
    
    This model captures the metadata of a blog post before content is fetched.
    Used in discovery and tracking phases.
    """
    id: str = Field(
        ...,
        description="Stable identifier, typically a hash of the URL"
    )
    url: HttpUrl = Field(
        ...,
        description="Full URL to the blog post"
    )
    title: str = Field(
        ...,
        description="Title of the blog post",
        min_length=1
    )
    published_at: Optional[datetime] = Field(
        None,
        description="Publication timestamp if available"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags or categories associated with the post"
    )
    source: str = Field(
        default="nvidia_tech_blog",
        description="Source identifier for the blog"
    )
    content: Optional[str] = Field(
        None,
        description="Full HTML content from RSS feed (if available). When present, avoids fetching individual post pages."
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Ensure ID is non-empty."""
        if not v or not v.strip():
            raise ValueError("ID cannot be empty")
        return v.strip()

    @model_serializer
    def serialize_model(self):
        """Custom serialization for JSON compatibility."""
        data = dict(self)
        if self.published_at:
            data["published_at"] = self.published_at.isoformat()
        return data

    model_config = ConfigDict(
        # Allow population by field name or alias
        populate_by_name=True,
        # Serialize HttpUrl as string
        str_strip_whitespace=True,
    )


class RawBlogContent(BaseModel):
    """Raw content extracted from a blog post HTML.
    
    This model represents the parsed HTML content before summarization.
    Used in the scraping phase.
    """
    blog_id: str = Field(
        ...,
        description="Reference to the BlogPost.id"
    )
    url: HttpUrl = Field(
        ...,
        description="URL of the source blog post"
    )
    title: str = Field(
        ...,
        description="Title extracted from the HTML"
    )
    html: str = Field(
        ...,
        description="Raw HTML content of the blog post"
    )
    text: str = Field(
        ...,
        description="Plain text extracted from HTML (main article content)"
    )
    sections: List[str] = Field(
        default_factory=list,
        description="Logical sections of the blog post (headings, paragraphs, etc.)"
    )
    categories: List[str] = Field(
        default_factory=list,
        description="Categories or tags associated with the blog post (from discovery phase)"
    )

    @field_validator("blog_id", "title", "text")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        """Ensure critical string fields are non-empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class BlogSummary(BaseModel):
    """Structured summary of a blog post.
    
    This model represents the AI-generated summary that will be ingested
    into the RAG backend. Used in summarization and ingestion phases.
    """
    blog_id: str = Field(
        ...,
        description="Reference to the BlogPost.id"
    )
    title: str = Field(
        ...,
        description="Title of the blog post"
    )
    url: HttpUrl = Field(
        ...,
        description="URL of the source blog post"
    )
    published_at: Optional[datetime] = Field(
        None,
        description="Publication timestamp"
    )
    executive_summary: str = Field(
        ...,
        description="High-level executive summary (1-3 sentences)",
        min_length=10
    )
    technical_summary: str = Field(
        ...,
        description="Detailed technical summary (2-5 paragraphs)",
        min_length=50
    )
    bullet_points: List[str] = Field(
        default_factory=list,
        description="Key takeaways in bullet point format"
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="Relevant keywords and topics for searchability"
    )

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, v: List[str]) -> List[str]:
        """Normalize keywords to lowercase and remove duplicates."""
        if not v:
            return []
        normalized = [kw.strip().lower() for kw in v if kw.strip()]
        # Remove duplicates while preserving order
        seen = set()
        result = []
        for kw in normalized:
            if kw not in seen:
                seen.add(kw)
                result.append(kw)
        return result

    def to_rag_document(self) -> str:
        """Convert summary to a single document string for RAG ingestion.
        
        Returns:
            A formatted string containing all summary fields.
        """
        parts = [
            f"Title: {self.title}",
            f"URL: {self.url}",
            "",
            "Executive Summary:",
            self.executive_summary,
            "",
            "Technical Summary:",
            self.technical_summary,
        ]
        
        if self.bullet_points:
            parts.extend([
                "",
                "Key Points:",
                *[f"• {point}" for point in self.bullet_points]
            ])
        
        if self.keywords:
            # Separate categories (if they look like categories) from other keywords
            # Categories are typically longer, multi-word phrases like "Agentic AI / Generative AI"
            categories = [kw for kw in self.keywords if "/" in kw or len(kw.split()) > 2]
            other_keywords = [kw for kw in self.keywords if kw not in categories]
            
            if categories:
                parts.extend([
                    "",
                    f"Categories: {', '.join(categories)}"
                ])
            if other_keywords:
                parts.extend([
                    "",
                    f"Keywords: {', '.join(other_keywords)}"
                ])
        
        if self.published_at:
            parts.insert(2, f"Published: {self.published_at.isoformat()}")
        
        return "\n".join(parts)

    @model_serializer
    def serialize_model(self):
        """Custom serialization for JSON compatibility."""
        data = dict(self)
        if self.published_at:
            data["published_at"] = self.published_at.isoformat()
        return data

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class RetrievedDoc(BaseModel):
    """Document retrieved from RAG backend for answering queries.
    
    This model represents a document returned by the RAG retrieval system.
    Used in the QA agent phase.
    """
    blog_id: str = Field(
        ...,
        description="Reference to the BlogPost.id"
    )
    title: str = Field(
        ...,
        description="Title of the retrieved blog post"
    )
    url: HttpUrl = Field(
        ...,
        description="URL of the source blog post"
    )
    snippet: str = Field(
        ...,
        description="Relevant text snippet from the document",
        min_length=1
    )
    score: float = Field(
        ...,
        description="Relevance score from the retrieval system",
        ge=0.0,
        le=1.0
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
            description="Additional metadata from the retrieval system"
    )

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
    )


# Utility functions for working with these models

def generate_post_id(url: str) -> str:
    """Generate a deterministic, stable ID for a blog post URL.
    
    Args:
        url: The blog post URL
        
    Returns:
        A SHA256 hash of the URL as a hexadecimal string
        
    Example:
        >>> generate_post_id("https://developer.nvidia.com/blog/example")
        'a1b2c3d4e5f6...'
    """
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def blog_summary_to_dict(summary: BlogSummary) -> Dict[str, Any]:
    """Convert BlogSummary to a dictionary suitable for RAG ingestion.
    
    Args:
        summary: The BlogSummary to convert
        
    Returns:
        Dictionary with fields formatted for RAG backend ingestion
    """
    return {
        "document": summary.to_rag_document(),
        "doc_index": summary.blog_id,
        "doc_metadata": {
            "blog_id": summary.blog_id,
            "title": summary.title,
            "url": str(summary.url),
            "published_at": summary.published_at.isoformat() if summary.published_at else None,
            "keywords": summary.keywords,
            "source": "nvidia_tech_blog",
        },
    }

