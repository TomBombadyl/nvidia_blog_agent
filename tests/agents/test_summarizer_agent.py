"""Unit tests for SummarizerAgent.

Tests cover:
- SummarizerAgentStub: Testable stub implementation
- Agent processing logic with mock LLM responses
- State reading and writing
- Error handling
"""

import pytest
import json
from nvidia_blog_agent.contracts.blog_models import RawBlogContent, BlogSummary
from nvidia_blog_agent.agents.summarizer_agent import SummarizerAgentStub


class MockSession:
    """Mock session object for testing."""

    def __init__(self, initial_state=None):
        self.state = initial_state or {}


class TestSummarizerAgentStub:
    """Tests for SummarizerAgentStub (testable version)."""

    def test_process_single_raw_content(self):
        """Test processing a single RawBlogContent."""
        raw = RawBlogContent(
            blog_id="test-id-123",
            url="https://developer.nvidia.com/blog/test",
            title="Test Blog Post",
            html="<html>Test</html>",
            text="This is a test blog post about AI and machine learning.",
        )

        def mock_llm(prompt: str) -> str:
            return json.dumps(
                {
                    "executive_summary": "This blog post discusses AI and machine learning.",
                    "technical_summary": "This blog post provides a comprehensive overview of artificial intelligence and machine learning technologies, covering key concepts and implementation details.",
                    "bullet_points": ["AI is important", "ML is useful"],
                    "keywords": ["AI", "ML"],
                }
            )

        agent = SummarizerAgentStub(mock_llm)
        session = MockSession({"raw_blog_contents": [raw]})

        agent.process(session)

        assert "blog_summaries" in session.state
        summaries = session.state["blog_summaries"]
        assert len(summaries) == 1

        summary = summaries[0]
        assert isinstance(summary, BlogSummary)
        assert summary.blog_id == "test-id-123"
        assert summary.title == "Test Blog Post"
        assert (
            "AI" in summary.executive_summary
            or "machine learning" in summary.executive_summary.lower()
        )
        assert len(summary.bullet_points) == 2
        assert "ai" in summary.keywords

    def test_process_multiple_raw_contents(self):
        """Test processing multiple RawBlogContent objects."""
        raw1 = RawBlogContent(
            blog_id="test-id-1",
            url="https://example.com/post1",
            title="Post 1",
            html="<html>Test1</html>",
            text="Content 1",
        )
        raw2 = RawBlogContent(
            blog_id="test-id-2",
            url="https://example.com/post2",
            title="Post 2",
            html="<html>Test2</html>",
            text="Content 2",
        )

        call_count = 0

        def mock_llm(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            return json.dumps(
                {
                    "executive_summary": f"Summary {call_count}.",
                    "technical_summary": f"Technical summary {call_count} with enough content to meet validation requirements.",
                    "bullet_points": [],
                    "keywords": [],
                }
            )

        agent = SummarizerAgentStub(mock_llm)
        session = MockSession({"raw_blog_contents": [raw1, raw2]})

        agent.process(session)

        summaries = session.state["blog_summaries"]
        assert len(summaries) == 2
        assert call_count == 2
        assert summaries[0].blog_id == "test-id-1"
        assert summaries[1].blog_id == "test-id-2"

    def test_process_empty_list(self):
        """Test processing when raw_blog_contents is empty."""
        agent = SummarizerAgentStub(lambda p: "{}")
        session = MockSession({"raw_blog_contents": []})

        agent.process(session)

        assert session.state["blog_summaries"] == []

    def test_process_missing_key(self):
        """Test processing when raw_blog_contents key is missing."""
        agent = SummarizerAgentStub(lambda p: "{}")
        session = MockSession({})  # No raw_blog_contents key

        agent.process(session)

        assert session.state["blog_summaries"] == []

    def test_process_dict_input(self):
        """Test processing when raw_blog_contents contains dicts instead of objects."""
        raw_dict = {
            "blog_id": "test-id-123",
            "url": "https://example.com/post",
            "title": "Test Post",
            "html": "<html>Test</html>",
            "text": "Content here",
        }

        def mock_llm(prompt: str) -> str:
            return json.dumps(
                {
                    "executive_summary": "This is a valid executive summary that meets the minimum length requirement.",
                    "technical_summary": "Technical summary with enough content to meet validation requirements.",
                }
            )

        agent = SummarizerAgentStub(mock_llm)
        session = MockSession({"raw_blog_contents": [raw_dict]})

        agent.process(session)

        summaries = session.state["blog_summaries"]
        assert len(summaries) == 1
        assert summaries[0].blog_id == "test-id-123"

    def test_process_with_custom_max_text_chars(self):
        """Test that custom max_text_chars is used in prompt building."""
        long_text = "A" * 5000
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text=long_text,
        )

        prompts_received = []

        def mock_llm(prompt: str) -> str:
            prompts_received.append(prompt)
            return json.dumps(
                {
                    "executive_summary": "This is a valid executive summary that meets the minimum length requirement.",
                    "technical_summary": "Technical summary with enough content to meet validation requirements and provide comprehensive details.",
                }
            )

        agent = SummarizerAgentStub(mock_llm, max_text_chars=1000)
        session = MockSession({"raw_blog_contents": [raw]})

        agent.process(session)

        # Check that prompt was truncated (rough check)
        assert len(prompts_received) == 1
        # The prompt should be shorter than if we included all 5000 chars
        assert len(prompts_received[0]) < 6000

    def test_process_llm_returns_markdown_wrapped_json(self):
        """Test that agent handles markdown-wrapped JSON responses."""
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text="Content",
        )

        def mock_llm(prompt: str) -> str:
            return """```json
{
  "executive_summary": "Summary here.",
  "technical_summary": "Technical summary with enough content to meet validation requirements."
}
```"""

        agent = SummarizerAgentStub(mock_llm)
        session = MockSession({"raw_blog_contents": [raw]})

        agent.process(session)

        summaries = session.state["blog_summaries"]
        assert len(summaries) == 1
        assert summaries[0].executive_summary == "Summary here."

    def test_process_llm_returns_invalid_json(self):
        """Test that agent raises error when LLM returns invalid JSON."""
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text="Content",
        )

        def mock_llm(prompt: str) -> str:
            return "This is not JSON at all!"

        agent = SummarizerAgentStub(mock_llm)
        session = MockSession({"raw_blog_contents": [raw]})

        with pytest.raises(ValueError) as exc_info:
            agent.process(session)

        assert "Failed to parse JSON" in str(exc_info.value)

    def test_process_preserves_blog_metadata(self):
        """Test that blog metadata (id, title, url) is preserved in summary."""
        raw = RawBlogContent(
            blog_id="unique-id-789",
            url="https://developer.nvidia.com/blog/specific-post",
            title="Specific Title",
            html="<html>Test</html>",
            text="Content",
        )

        def mock_llm(prompt: str) -> str:
            return json.dumps(
                {
                    "executive_summary": "This is a valid executive summary that meets the minimum length requirement.",
                    "technical_summary": "Technical summary with enough content to meet validation requirements and provide comprehensive details.",
                }
            )

        agent = SummarizerAgentStub(mock_llm)
        session = MockSession({"raw_blog_contents": [raw]})

        agent.process(session)

        summary = session.state["blog_summaries"][0]
        assert summary.blog_id == "unique-id-789"
        assert summary.title == "Specific Title"
        assert str(summary.url) == "https://developer.nvidia.com/blog/specific-post"

    def test_process_keyword_normalization(self):
        """Test that keywords are normalized (via BlogSummary validator)."""
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text="Content",
        )

        def mock_llm(prompt: str) -> str:
            return json.dumps(
                {
                    "executive_summary": "This is a valid executive summary that meets the minimum length requirement.",
                    "technical_summary": "Technical summary with enough content to meet validation requirements and provide comprehensive details.",
                    "keywords": ["AI", "ai", "CUDA", "  cuda  "],
                }
            )

        agent = SummarizerAgentStub(mock_llm)
        session = MockSession({"raw_blog_contents": [raw]})

        agent.process(session)

        summary = session.state["blog_summaries"][0]
        assert "ai" in summary.keywords
        assert "cuda" in summary.keywords
        assert len(summary.keywords) == 2  # Deduplicated

    def test_process_with_sections(self):
        """Test that agent processes RawBlogContent with sections."""
        raw = RawBlogContent(
            blog_id="test-id",
            url="https://example.com/post",
            title="Test Post",
            html="<html>Test</html>",
            text="Main content",
            sections=["Introduction\n\nIntro text", "Conclusion\n\nConclusion text"],
        )

        prompts_received = []

        def mock_llm(prompt: str) -> str:
            prompts_received.append(prompt)
            return json.dumps(
                {
                    "executive_summary": "This is a valid executive summary that meets the minimum length requirement.",
                    "technical_summary": "Technical summary with enough content to meet validation requirements and provide comprehensive details.",
                }
            )

        agent = SummarizerAgentStub(mock_llm)
        session = MockSession({"raw_blog_contents": [raw]})

        agent.process(session)

        # Check that sections were included in prompt
        assert len(prompts_received) == 1
        assert "Introduction" in prompts_received[0]
        assert "Conclusion" in prompts_received[0]
