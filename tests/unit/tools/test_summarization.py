"""Unit tests for summarization tools.

Tests cover:
- build_summary_prompt: Prompt construction and text truncation
- parse_summary_json: JSON parsing with various formats (plain JSON, markdown-wrapped, etc.)
"""

import pytest
import json
from nvidia_blog_agent.contracts.blog_models import RawBlogContent
from nvidia_blog_agent.tools.summarization import (
    build_summary_prompt,
    parse_summary_json,
)
from datetime import datetime
from pydantic import ValidationError


class TestBuildSummaryPrompt:
    """Tests for build_summary_prompt function."""

    def test_basic_prompt_construction(self):
        """Test that prompt includes title, URL, and content."""
        raw = RawBlogContent(
            blog_id="test-id-123",
            url="https://developer.nvidia.com/blog/test",
            title="Test Blog Post",
            html="<html>Test</html>",
            text="This is a test blog post about AI and machine learning.",
        )

        prompt = build_summary_prompt(raw)

        assert "Test Blog Post" in prompt
        assert "https://developer.nvidia.com/blog/test" in prompt
        assert "This is a test blog post" in prompt
        assert "executive_summary" in prompt.lower()
        assert "technical_summary" in prompt.lower()
        assert "bullet_points" in prompt.lower()
        assert "keywords" in prompt.lower()

    def test_prompt_includes_sections(self):
        """Test that prompt includes sections when available."""
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text="Main content here.",
            sections=["Introduction\n\nIntro text", "Conclusion\n\nConclusion text"],
        )

        prompt = build_summary_prompt(raw)

        assert "Section 1:" in prompt
        assert "Introduction" in prompt
        assert "Section 2:" in prompt
        assert "Conclusion" in prompt

    def test_prompt_without_sections(self):
        """Test that prompt works without sections."""
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text="Content here.",
            sections=[],
        )

        prompt = build_summary_prompt(raw)

        assert "Content here" in prompt
        assert "Section" not in prompt or "Structured Sections:" not in prompt

    def test_text_truncation(self):
        """Test that text is truncated when exceeding max_text_chars."""
        long_text = "A" * 5000  # 5000 characters
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text=long_text,
        )

        prompt = build_summary_prompt(raw, max_text_chars=4000)

        # Should be truncated to 4000 chars + "..."
        assert len(prompt) < len(long_text) + 1000  # Rough check
        assert "..." in prompt

    def test_text_no_truncation_when_short(self):
        """Test that text is not truncated when under limit."""
        short_text = "Short content."
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text=short_text,
        )

        prompt = build_summary_prompt(raw, max_text_chars=4000)

        assert short_text in prompt
        assert "..." not in prompt or prompt.count("...") == 1  # Only in instructions

    def test_prompt_json_format_instructions(self):
        """Test that prompt clearly instructs JSON format."""
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text="Content",
        )

        prompt = build_summary_prompt(raw)

        assert "JSON" in prompt
        assert "executive_summary" in prompt
        assert "technical_summary" in prompt
        assert "bullet_points" in prompt
        assert "keywords" in prompt
        prompt_lower = prompt.lower()
        assert "strict json" in prompt_lower or "valid json" in prompt_lower

    def test_custom_max_text_chars(self):
        """Test that custom max_text_chars parameter works."""
        long_text = "B" * 2000
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text=long_text,
        )

        prompt_short = build_summary_prompt(raw, max_text_chars=1000)
        prompt_long = build_summary_prompt(raw, max_text_chars=3000)

        # Both should include content, but short one should be truncated
        assert len(prompt_short) < len(prompt_long)


class TestParseSummaryJson:
    """Tests for parse_summary_json function."""

    def test_parse_valid_json(self):
        """Test parsing valid JSON response."""
        raw = RawBlogContent(
            blog_id="test-id-123",
            url="https://developer.nvidia.com/blog/test",
            title="Test Blog Post",
            html="<html>Test</html>",
            text="Content here",
        )

        json_str = json.dumps(
            {
                "executive_summary": "This is an executive summary of the blog post.",
                "technical_summary": "This is a detailed technical summary that provides comprehensive information about the topic and meets the minimum length requirement of 50 characters.",
                "bullet_points": ["Point 1", "Point 2", "Point 3"],
                "keywords": ["AI", "ML", "NVIDIA"],
            }
        )

        summary = parse_summary_json(raw, json_str)

        assert summary.blog_id == "test-id-123"
        assert summary.title == "Test Blog Post"
        assert summary.url == raw.url
        assert summary.executive_summary.startswith("This is an executive")
        assert len(summary.technical_summary) >= 50
        assert len(summary.bullet_points) == 3
        assert "ai" in summary.keywords  # Normalized to lowercase
        assert "ml" in summary.keywords
        assert summary.published_at is None

    def test_parse_json_with_published_at(self):
        """Test parsing JSON with published_at parameter."""
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text="Content",
        )

        published = datetime(2024, 1, 15, 10, 30, 0)
        json_str = json.dumps(
            {
                "executive_summary": "Executive summary here.",
                "technical_summary": "Technical summary with enough content to meet validation requirements and provide comprehensive details.",
            }
        )

        summary = parse_summary_json(raw, json_str, published_at=published)

        assert summary.published_at == published

    def test_parse_json_markdown_wrapped(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text="Content",
        )

        json_str = """```json
{
  "executive_summary": "Summary here.",
  "technical_summary": "Technical summary with enough content to meet validation requirements."
}
```"""

        summary = parse_summary_json(raw, json_str)

        assert summary.executive_summary == "Summary here."
        assert len(summary.technical_summary) >= 50

    def test_parse_json_with_leading_trailing_text(self):
        """Test parsing JSON that has extra text before/after."""
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text="Content",
        )

        json_str = """Here is the JSON:
{
  "executive_summary": "This is a valid executive summary that meets the minimum length requirement.",
  "technical_summary": "Technical summary with enough content to meet validation requirements and provide comprehensive details."
}
That's the summary."""

        summary = parse_summary_json(raw, json_str)

        assert summary.executive_summary.startswith("This is a valid")

    def test_parse_json_empty_bullet_points(self):
        """Test parsing JSON with empty bullet_points array."""
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text="Content",
        )

        json_str = json.dumps(
            {
                "executive_summary": "Summary here.",
                "technical_summary": "Technical summary with enough content to meet validation requirements.",
                "bullet_points": [],
                "keywords": [],
            }
        )

        summary = parse_summary_json(raw, json_str)

        assert summary.bullet_points == []
        assert summary.keywords == []

    def test_parse_json_keyword_normalization(self):
        """Test that keywords are normalized (handled by BlogSummary validator)."""
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text="Content",
        )

        json_str = json.dumps(
            {
                "executive_summary": "This is a valid executive summary that meets the minimum length requirement.",
                "technical_summary": "Technical summary with enough content to meet validation requirements and provide comprehensive details.",
                "keywords": ["AI", "ai", "CUDA", "  cuda  "],
            }
        )

        summary = parse_summary_json(raw, json_str)

        # BlogSummary validator normalizes keywords
        assert "ai" in summary.keywords
        assert "cuda" in summary.keywords
        assert len(summary.keywords) == 2  # Deduplicated

    def test_parse_json_invalid_format(self):
        """Test that invalid JSON raises ValueError."""
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text="Content",
        )

        invalid_json = "This is not JSON at all!"

        with pytest.raises(ValueError) as exc_info:
            parse_summary_json(raw, invalid_json)

        assert "Failed to parse JSON" in str(exc_info.value)

    def test_parse_json_missing_required_fields(self):
        """Test that missing fields use defaults or empty strings."""
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text="Content",
        )

        # Missing executive_summary and technical_summary
        json_str = json.dumps({"bullet_points": ["Point 1"]})

        # Should create BlogSummary but validation will fail for short summaries
        # So we expect ValidationError
        with pytest.raises(ValidationError):
            parse_summary_json(raw, json_str)

    def test_parse_json_non_list_bullet_points(self):
        """Test that non-list bullet_points are handled gracefully."""
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text="Content",
        )

        json_str = json.dumps(
            {
                "executive_summary": "Summary here.",
                "technical_summary": "Technical summary with enough content to meet validation requirements.",
                "bullet_points": "not a list",  # Should be converted to empty list
            }
        )

        summary = parse_summary_json(raw, json_str)

        assert summary.bullet_points == []

    def test_parse_json_non_list_keywords(self):
        """Test that non-list keywords are handled gracefully."""
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text="Content",
        )

        json_str = json.dumps(
            {
                "executive_summary": "Summary here.",
                "technical_summary": "Technical summary with enough content to meet validation requirements.",
                "keywords": "not a list",  # Should be converted to empty list
            }
        )

        summary = parse_summary_json(raw, json_str)

        assert summary.keywords == []

    def test_parse_json_preserves_blog_metadata(self):
        """Test that blog_id, title, and url are preserved from RawBlogContent."""
        raw = RawBlogContent(
            blog_id="unique-blog-id-456",
            url="https://developer.nvidia.com/blog/specific-post",
            title="Specific Blog Title",
            html="<html>Test</html>",
            text="Content",
        )

        json_str = json.dumps(
            {
                "executive_summary": "This is a valid executive summary that meets the minimum length requirement.",
                "technical_summary": "Technical summary with enough content to meet validation requirements and provide comprehensive details.",
            }
        )

        summary = parse_summary_json(raw, json_str)

        assert summary.blog_id == "unique-blog-id-456"
        assert summary.title == "Specific Blog Title"
        assert str(summary.url) == "https://developer.nvidia.com/blog/specific-post"
