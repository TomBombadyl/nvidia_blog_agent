"""Tests for the daily ingestion pipeline workflow.

Tests cover:
- Full pipeline execution with various scenarios
- Discovery and diffing logic
- Integration of all pipeline stages
- Edge cases (empty feeds, malformed posts, etc.)
"""

import pytest
from typing import List
from nvidia_blog_agent.contracts.blog_models import RawBlogContent, BlogSummary
from nvidia_blog_agent.agents.workflow import (
    run_ingestion_pipeline,
    discover_new_posts_from_feed,
    ingest_summaries,
    IngestionResult,
)


class StubFetcher:
    """Stub implementation of HtmlFetcher for testing."""

    def __init__(self, html_by_url: dict[str, str]):
        """Initialize stub with HTML content mapped by URL.

        Args:
            html_by_url: Dictionary mapping URL strings to HTML content strings.
        """
        self.html_by_url = html_by_url
        self.called_urls: List[str] = []

    async def fetch_html(self, url: str) -> str:
        """Fetch HTML for a URL (stub implementation).

        Args:
            url: URL to fetch HTML for.

        Returns:
            HTML content from html_by_url dictionary.
        """
        self.called_urls.append(url)
        return self.html_by_url[url]


class StubSummarizer:
    """Stub implementation of SummarizerLike for testing."""

    def __init__(self):
        """Initialize stub summarizer."""
        self.calls: List[List[RawBlogContent]] = []

    async def summarize(self, contents: List[RawBlogContent]) -> List[BlogSummary]:
        """Summarize RawBlogContent objects (stub implementation).

        Args:
            contents: List of RawBlogContent objects to summarize.

        Returns:
            List of BlogSummary objects with synthetic summaries.
        """
        self.calls.append(contents)
        summaries: List[BlogSummary] = []
        for raw in contents:
            summaries.append(
                BlogSummary(
                    blog_id=raw.blog_id,
                    title=raw.title,
                    url=raw.url,
                    published_at=None,
                    executive_summary=f"Exec summary of {raw.title}",
                    technical_summary=f"Technical summary of {raw.title} with enough content to meet validation requirements.",
                    bullet_points=[f"Point for {raw.title}"],
                    keywords=["nvidia", "blog"],
                )
            )
        return summaries


class StubRagClient:
    """Stub implementation of RagIngestClient for testing."""

    def __init__(self):
        """Initialize stub RAG client."""
        self.ingested: List[BlogSummary] = []

    async def ingest_summary(self, summary: BlogSummary) -> None:
        """Ingest a BlogSummary (stub implementation).

        Args:
            summary: BlogSummary object to ingest.
        """
        self.ingested.append(summary)


def create_feed_html() -> str:
    """Create a simple feed HTML fixture with two posts.

    Returns:
        HTML string containing two blog posts that can be parsed by discover_posts_from_feed.
    """
    return """
    <html>
        <body>
            <div class="post">
                <a class="post-link" href="https://developer.nvidia.com/blog/post1">First Blog Post</a>
                <time datetime="2024-01-15T10:00:00Z">January 15, 2024</time>
            </div>
            <div class="post">
                <a class="post-link" href="https://developer.nvidia.com/blog/post2">Second Blog Post</a>
                <time datetime="2024-01-16T10:00:00Z">January 16, 2024</time>
            </div>
        </body>
    </html>
    """


class TestDiscoverNewPostsFromFeed:
    """Tests for discover_new_posts_from_feed helper."""

    def test_no_existing_ids_treats_all_as_new(self):
        """Test that when existing_ids is None, all discovered posts are treated as new."""
        feed = create_feed_html()
        discovered, new = discover_new_posts_from_feed(feed, existing_ids=None)

        assert len(discovered) == 2
        assert len(new) == 2
        assert discovered == new

    def test_with_existing_ids_filters_correctly(self):
        """Test that existing_ids correctly filters out already-seen posts."""
        feed = create_feed_html()
        discovered, _ = discover_new_posts_from_feed(feed, existing_ids=None)

        # Use the ID of the first post as existing
        existing_id = discovered[0].id
        _, new = discover_new_posts_from_feed(feed, existing_ids=[existing_id])

        assert len(new) == 1
        assert new[0].id == discovered[1].id


class TestFullPipeline:
    """Tests for the complete ingestion pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_no_existing_ids(self):
        """Test full pipeline when no existing_ids are provided."""
        feed_html = create_feed_html()

        # Create stub dependencies
        html_by_url = {
            "https://developer.nvidia.com/blog/post1": "<html><body><article><h1>Post 1</h1><p>Content 1</p></article></body></html>",
            "https://developer.nvidia.com/blog/post2": "<html><body><article><h1>Post 2</h1><p>Content 2</p></article></body></html>",
        }
        fetcher = StubFetcher(html_by_url)
        summarizer = StubSummarizer()
        rag_client = StubRagClient()

        # Run pipeline
        result = await run_ingestion_pipeline(
            feed_html,
            existing_ids=None,
            fetcher=fetcher,
            summarizer=summarizer,
            rag_client=rag_client,
        )

        # Assertions
        assert isinstance(result, IngestionResult)
        assert len(result.discovered_posts) == 2
        assert len(result.new_posts) == 2
        assert result.discovered_posts == result.new_posts

        assert len(result.raw_contents) == 2
        assert len(result.summaries) == 2

        # Verify fetcher was called for both posts
        assert len(fetcher.called_urls) == 2
        assert "https://developer.nvidia.com/blog/post1" in fetcher.called_urls
        assert "https://developer.nvidia.com/blog/post2" in fetcher.called_urls

        # Verify summarizer was called once with all raw contents
        assert len(summarizer.calls) == 1
        assert len(summarizer.calls[0]) == 2

        # Verify RAG client ingested all summaries
        assert len(rag_client.ingested) == 2
        assert rag_client.ingested[0].blog_id == result.summaries[0].blog_id
        assert rag_client.ingested[1].blog_id == result.summaries[1].blog_id

    @pytest.mark.asyncio
    async def test_full_pipeline_with_existing_ids_filtering(self):
        """Test full pipeline when existing_ids filters out some posts."""
        feed_html = create_feed_html()

        # Discover posts to get their IDs
        discovered, _ = discover_new_posts_from_feed(feed_html, existing_ids=None)
        existing_id = discovered[0].id  # Mark first post as existing

        # Create stub dependencies
        html_by_url = {
            "https://developer.nvidia.com/blog/post2": "<html><body><article><h1>Post 2</h1><p>Content 2</p></article></body></html>",
        }
        fetcher = StubFetcher(html_by_url)
        summarizer = StubSummarizer()
        rag_client = StubRagClient()

        # Run pipeline
        result = await run_ingestion_pipeline(
            feed_html,
            existing_ids=[existing_id],
            fetcher=fetcher,
            summarizer=summarizer,
            rag_client=rag_client,
        )

        # Assertions
        assert len(result.discovered_posts) == 2  # All posts discovered
        assert len(result.new_posts) == 1  # Only one new post
        assert result.new_posts[0].id == discovered[1].id

        assert len(result.raw_contents) == 1  # Only processed new post
        assert len(result.summaries) == 1

        # Verify fetcher was only called for the new post
        assert len(fetcher.called_urls) == 1
        assert "https://developer.nvidia.com/blog/post2" in fetcher.called_urls

        # Verify summarizer was called with only the new post's content
        assert len(summarizer.calls) == 1
        assert len(summarizer.calls[0]) == 1

        # Verify RAG client only ingested the new post's summary
        assert len(rag_client.ingested) == 1

    @pytest.mark.asyncio
    async def test_empty_feed_html(self):
        """Test pipeline with empty feed HTML."""
        feed_html = "<html><body></body></html>"

        fetcher = StubFetcher({})
        summarizer = StubSummarizer()
        rag_client = StubRagClient()

        result = await run_ingestion_pipeline(
            feed_html,
            existing_ids=None,
            fetcher=fetcher,
            summarizer=summarizer,
            rag_client=rag_client,
        )

        # All lists should be empty
        assert len(result.discovered_posts) == 0
        assert len(result.new_posts) == 0
        assert len(result.raw_contents) == 0
        assert len(result.summaries) == 0

        # No calls to dependencies
        assert len(fetcher.called_urls) == 0
        assert len(summarizer.calls) == 0
        assert len(rag_client.ingested) == 0

    @pytest.mark.asyncio
    async def test_feed_with_malformed_post(self):
        """Test pipeline handles malformed posts gracefully."""
        feed_html = """
        <html>
            <body>
                <div class="post">
                    <a class="post-link" href="https://developer.nvidia.com/blog/valid">Valid Post</a>
                    <time datetime="2024-01-15T10:00:00Z">January 15, 2024</time>
                </div>
                <div class="post">
                    <!-- Malformed: missing link -->
                    <time datetime="2024-01-16T10:00:00Z">January 16, 2024</time>
                </div>
            </body>
        </html>
        """

        html_by_url = {
            "https://developer.nvidia.com/blog/valid": "<html><body><article><h1>Valid</h1><p>Content</p></article></body></html>",
        }
        fetcher = StubFetcher(html_by_url)
        summarizer = StubSummarizer()
        rag_client = StubRagClient()

        result = await run_ingestion_pipeline(
            feed_html,
            existing_ids=None,
            fetcher=fetcher,
            summarizer=summarizer,
            rag_client=rag_client,
        )

        # Should only process the valid post
        assert len(result.discovered_posts) == 1
        assert len(result.new_posts) == 1
        assert len(result.raw_contents) == 1
        assert len(result.summaries) == 1

        # Should only call fetcher for valid post
        assert len(fetcher.called_urls) == 1


class TestIngestSummaries:
    """Tests for ingest_summaries helper."""

    @pytest.mark.asyncio
    async def test_ingest_summaries_calls_client_for_each(self):
        """Test that ingest_summaries calls rag_client for each summary."""
        summaries = [
            BlogSummary(
                blog_id="id1",
                title="Summary 1",
                url="https://example.com/1",
                executive_summary="Executive summary 1 with enough content.",
                technical_summary="Technical summary 1 with enough content to meet validation requirements.",
            ),
            BlogSummary(
                blog_id="id2",
                title="Summary 2",
                url="https://example.com/2",
                executive_summary="Executive summary 2 with enough content.",
                technical_summary="Technical summary 2 with enough content to meet validation requirements.",
            ),
        ]

        rag_client = StubRagClient()

        await ingest_summaries(summaries, rag_client)

        assert len(rag_client.ingested) == 2
        assert rag_client.ingested[0].blog_id == "id1"
        assert rag_client.ingested[1].blog_id == "id2"

    @pytest.mark.asyncio
    async def test_ingest_summaries_empty_list(self):
        """Test that ingest_summaries handles empty list gracefully."""
        rag_client = StubRagClient()

        await ingest_summaries([], rag_client)

        assert len(rag_client.ingested) == 0
