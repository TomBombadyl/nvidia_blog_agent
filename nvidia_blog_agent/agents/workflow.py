"""Workflow orchestration for the NVIDIA Blog Agent ingestion pipeline.

This module provides:
- IngestionResult: Dataclass for pipeline outputs
- SummarizerLike Protocol: Abstract interface for summarization
- Pipeline stage helpers: Discovery, scraping, summarization, ingestion
- run_ingestion_pipeline: Main orchestrator function

The workflow orchestrates:
1. Discovery: Parse feed HTML → BlogPost objects, diff against existing IDs
2. Scraping: Fetch and parse HTML for new posts → RawBlogContent
3. Summarization: Convert RawBlogContent → BlogSummary
4. Ingestion: Send BlogSummary objects to RAG backend

All external dependencies (HtmlFetcher, SummarizerLike, RagIngestClient) are injected,
making the workflow fully testable and adaptable to different implementations.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Iterable, Protocol, Optional
from nvidia_blog_agent.contracts.blog_models import BlogPost, RawBlogContent, BlogSummary
from nvidia_blog_agent.tools.discovery import discover_posts_from_feed, diff_new_posts
from nvidia_blog_agent.tools.scraper import HtmlFetcher, fetch_and_parse_blog
from nvidia_blog_agent.tools.rag_ingest import RagIngestClient

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result of running the ingestion pipeline.
    
    Attributes:
        discovered_posts: All posts found in the feed (before diffing against existing IDs).
        new_posts: Posts that are actually new (after diffing against existing IDs).
        raw_contents: Parsed RawBlogContent objects for new_posts.
        summaries: BlogSummary objects produced for raw_contents.
    """
    discovered_posts: List[BlogPost]
    new_posts: List[BlogPost]
    raw_contents: List[RawBlogContent]
    summaries: List[BlogSummary]


class SummarizerLike(Protocol):
    """Protocol for summarization implementations.
    
    This abstract interface allows the workflow to work with various summarization
    implementations:
    - ADK SummarizerAgent wrappers
    - Direct LLM calls
    - Test stubs for testing
    
    Implementations must provide an async summarize method that takes a list of
    RawBlogContent objects and returns a list of BlogSummary objects.
    """
    
    async def summarize(self, contents: List[RawBlogContent]) -> List[BlogSummary]:
        """Summarize a batch of RawBlogContent objects into BlogSummary objects.
        
        Args:
            contents: List of RawBlogContent objects to summarize.
        
        Returns:
            List of BlogSummary objects, one per input RawBlogContent.
        """
        ...


def discover_new_posts_from_feed(
    feed_html: str,
    existing_ids: Optional[Iterable[str]] = None,
) -> tuple[List[BlogPost], List[BlogPost]]:
    """Parse the feed HTML, then diff against existing_ids to find new posts.
    
    This function combines discovery and diffing into a single step:
    1. Parses feed_html using discover_posts_from_feed()
    2. Filters discovered posts against existing_ids using diff_new_posts()
    
    If existing_ids is None, all discovered posts are treated as new.
    
    Args:
        feed_html: Raw HTML string containing the blog feed.
        existing_ids: Optional iterable of blog post IDs that have already been processed.
                     If None, all discovered posts are treated as new.
    
    Returns:
        Tuple of (discovered_posts, new_posts), where:
        - discovered_posts: All posts found in the feed
        - new_posts: Posts not in existing_ids (or all discovered if existing_ids is None)
    
    Example:
        >>> feed = "<html>...</html>"
        >>> existing = ["id1", "id2"]
        >>> discovered, new = discover_new_posts_from_feed(feed, existing)
        >>> len(new) <= len(discovered)
        True
    """
    discovered = discover_posts_from_feed(feed_html)
    
    if existing_ids is None:
        # If no history provided, treat all as new
        return discovered, discovered
    
    new_posts = diff_new_posts(existing_ids, discovered)
    return discovered, new_posts


async def fetch_raw_contents_for_posts(
    posts: List[BlogPost],
    fetcher: HtmlFetcher,
) -> List[RawBlogContent]:
    """Fetch and parse HTML for each BlogPost into RawBlogContent.
    
    This function processes multiple posts concurrently using asyncio.gather,
    making it efficient for batch processing. Each post is fetched and parsed
    independently. If a post fails to fetch (e.g., 403 Forbidden, 404 Not Found),
    it is skipped and logged, but processing continues for other posts.
    
    Args:
        posts: List of BlogPost objects to fetch and parse.
        fetcher: HtmlFetcher implementation to use for fetching HTML.
    
    Returns:
        List of RawBlogContent objects, one per successfully fetched BlogPost.
        May be shorter than the input posts list if some posts failed to fetch.
    
    Example:
        >>> posts = [BlogPost(id="1", url="https://example.com/1", title="Post 1")]
        >>> fetcher = SomeHtmlFetcher()
        >>> contents = await fetch_raw_contents_for_posts(posts, fetcher)
        >>> len(contents) <= len(posts)
        True
    """
    if not posts:
        return []
    
    async def fetch_with_error_handling(post: BlogPost) -> Optional[RawBlogContent]:
        """Fetch a single post, returning None if it fails."""
        try:
            return await fetch_and_parse_blog(post, fetcher)
        except Exception as e:
            logger.warning(
                f"Failed to fetch blog post '{post.title}' ({post.url}): {e}. Skipping."
            )
            return None
    
    tasks = [fetch_with_error_handling(post) for post in posts]
    results = await asyncio.gather(*tasks)
    
    # Filter out None results (failed fetches)
    return [content for content in results if content is not None]


async def summarize_raw_contents(
    contents: List[RawBlogContent],
    summarizer: SummarizerLike,
) -> List[BlogSummary]:
    """Use the provided summarizer to convert RawBlogContent objects into BlogSummary objects.
    
    This function delegates to the injected summarizer implementation, which may:
    - Call an LLM for each content
    - Batch process multiple contents
    - Use a test stub for testing
    
    Args:
        contents: List of RawBlogContent objects to summarize.
        summarizer: SummarizerLike implementation to use for summarization.
    
    Returns:
        List of BlogSummary objects, one per input RawBlogContent.
        Order matches the input contents list.
    
    Example:
        >>> contents = [RawBlogContent(...)]
        >>> summarizer = SomeSummarizer()
        >>> summaries = await summarize_raw_contents(contents, summarizer)
        >>> len(summaries) == len(contents)
        True
    """
    if not contents:
        return []
    
    return await summarizer.summarize(contents)


async def ingest_summaries(
    summaries: List[BlogSummary],
    rag_client: RagIngestClient,
) -> None:
    """Ingest each BlogSummary into the RAG backend.
    
    This function processes summaries sequentially, ingesting each one into
    the RAG backend. Failures in one ingestion don't stop the process,
    but exceptions are propagated to the caller.
    
    Args:
        summaries: List of BlogSummary objects to ingest.
        rag_client: RagIngestClient implementation to use for ingestion.
    
    Raises:
        Implementation-specific exceptions from rag_client.ingest_summary()
        (e.g., httpx.HTTPStatusError for HTTP failures).
    
    Example:
        >>> summaries = [BlogSummary(...)]
        >>> client = HttpRagIngestClient(...)
        >>> await ingest_summaries(summaries, client)
    """
    for summary in summaries:
        await rag_client.ingest_summary(summary)


async def run_ingestion_pipeline(
    feed_html: str,
    *,
    existing_ids: Optional[Iterable[str]] = None,
    fetcher: HtmlFetcher,
    summarizer: SummarizerLike,
    rag_client: RagIngestClient,
) -> IngestionResult:
    """Run the end-to-end ingestion pipeline.
    
    This function orchestrates the complete ingestion workflow:
    1. Discover posts from feed_html
    2. Diff against existing_ids to find truly new posts
    3. Fetch and parse HTML for new posts (concurrently)
    4. Summarize raw contents
    5. Ingest summaries into RAG backend
    
    All external interactions are handled through injected dependencies:
    - HtmlFetcher for fetching HTML
    - SummarizerLike for summarization
    - RagIngestClient for RAG ingestion
    
    Args:
        feed_html: Raw HTML string containing the blog feed.
        existing_ids: Optional iterable of blog post IDs that have already been processed.
                     If None, all discovered posts are treated as new.
        fetcher: HtmlFetcher implementation for fetching blog post HTML.
        summarizer: SummarizerLike implementation for generating summaries.
        rag_client: RagIngestClient implementation for ingesting summaries into RAG.
    
    Returns:
        IngestionResult containing:
        - discovered_posts: All posts found in the feed
        - new_posts: Posts that were actually new (not in existing_ids)
        - raw_contents: Parsed RawBlogContent for new_posts
        - summaries: BlogSummary objects produced for raw_contents
    
    Example:
        >>> feed = "<html>...</html>"
        >>> fetcher = HttpHtmlFetcher()
        >>> summarizer = SummarizerAgentWrapper()
        >>> rag_client = HttpRagIngestClient(...)
        >>> result = await run_ingestion_pipeline(
        ...     feed,
        ...     existing_ids=["id1", "id2"],
        ...     fetcher=fetcher,
        ...     summarizer=summarizer,
        ...     rag_client=rag_client
        ... )
        >>> len(result.new_posts) <= len(result.discovered_posts)
        True
    """
    # Stage 1: Discovery
    discovered_posts, new_posts = discover_new_posts_from_feed(feed_html, existing_ids)
    
    # Stage 2: Scraping (concurrent)
    raw_contents: List[RawBlogContent] = await fetch_raw_contents_for_posts(new_posts, fetcher)
    
    # Stage 3: Summarization
    summaries: List[BlogSummary] = await summarize_raw_contents(raw_contents, summarizer)
    
    # Stage 4: Ingestion
    await ingest_summaries(summaries, rag_client)
    
    return IngestionResult(
        discovered_posts=discovered_posts,
        new_posts=new_posts,
        raw_contents=raw_contents,
        summaries=summaries,
    )

