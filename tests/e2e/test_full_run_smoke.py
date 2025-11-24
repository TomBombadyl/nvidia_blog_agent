"""End-to-end smoke tests for the complete ingestion and QA pipeline.

Tests cover:
- Full pipeline from feed HTML → ingestion → state management → QA → evaluation
- Integration of all phases (discovery, scraping, summarization, ingestion, retrieval, QA)
- State helpers (existing IDs, metadata, history, compaction)
- In-memory RAG backend for self-contained testing
"""

import pytest
from typing import List, Dict
from nvidia_blog_agent.contracts.blog_models import (
    BlogPost,
    RawBlogContent,
    BlogSummary,
    RetrievedDoc,
)
from nvidia_blog_agent.tools.scraper import HtmlFetcher
from nvidia_blog_agent.tools.rag_ingest import RagIngestClient
from nvidia_blog_agent.tools.rag_retrieve import RagRetrieveClient
from nvidia_blog_agent.agents.workflow import (
    run_ingestion_pipeline,
    SummarizerLike,
    IngestionResult,
)
from nvidia_blog_agent.agents.qa_agent import QAAgent, QaModelLike
from nvidia_blog_agent.context.session_config import (
    get_existing_ids_from_state,
    update_existing_ids_in_state,
    store_last_ingestion_result_metadata,
    get_last_ingestion_result_metadata,
)
from nvidia_blog_agent.context.compaction import (
    append_ingestion_history_entry,
    compact_ingestion_history,
    INGESTION_HISTORY_KEY,
)
from nvidia_blog_agent.eval.harness import (
    EvalCase,
    run_qa_evaluation,
    summarize_eval_results,
)


class InMemoryRag(RagIngestClient, RagRetrieveClient):
    """In-memory RAG backend for end-to-end testing.
    
    This stub implements both RagIngestClient and RagRetrieveClient interfaces,
    storing summaries in memory and providing simple keyword-based retrieval.
    """
    
    def __init__(self):
        """Initialize in-memory RAG backend."""
        self.summaries: List[BlogSummary] = []
    
    async def ingest_summary(self, summary: BlogSummary) -> None:
        """Ingest a BlogSummary into the in-memory store.
        
        Args:
            summary: BlogSummary object to store.
        """
        self.summaries.append(summary)
    
    async def retrieve(self, query: str, k: int = 5) -> List[RetrievedDoc]:
        """Retrieve documents matching the query.
        
        Simple keyword-based retrieval: returns docs whose title or keywords
        contain any significant word from the query (case-insensitive).
        
        Args:
            query: Search query string.
            k: Maximum number of documents to retrieve.
        
        Returns:
            List of RetrievedDoc objects, up to k items.
        """
        docs: List[RetrievedDoc] = []
        query_lower = query.lower()
        # Extract significant words (skip common words)
        query_words = [w for w in query_lower.split() if len(w) > 2 and w not in ["the", "what", "did", "say", "about", "tell", "me"]]
        
        for s in self.summaries:
            # Check if any query word matches title or keywords
            text = f"{s.title} {' '.join(s.keywords)}".lower()
            if any(word in text for word in query_words) or query_lower in text:
                docs.append(
                    RetrievedDoc(
                        blog_id=s.blog_id,
                        title=s.title,
                        url=s.url,
                        snippet=s.executive_summary,
                        score=1.0,
                        metadata={"keywords": s.keywords},
                    )
                )
            if len(docs) >= k:
                break
        
        return docs


class StubFetcher:
    """Stub HtmlFetcher for testing."""
    
    def __init__(self, html_by_url: Dict[str, str]):
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
    """Stub SummarizerLike for testing."""
    
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
            # Extract keywords from title (simple heuristic)
            keywords = ["nvidia", "blog"]
            if "rag" in raw.title.lower():
                keywords.append("rag")
            if "gpu" in raw.title.lower():
                keywords.append("gpu")
            
            summaries.append(
                BlogSummary(
                    blog_id=raw.blog_id,
                    title=raw.title,
                    url=raw.url,
                    published_at=None,
                    executive_summary=f"Executive summary of {raw.title}",
                    technical_summary=f"Technical summary of {raw.title} with enough content to meet validation requirements and provide comprehensive details.",
                    bullet_points=[f"Key point about {raw.title}"],
                    keywords=keywords,
                )
            )
        
        return summaries


class StubQaModel:
    """Stub QaModelLike for testing."""
    
    def __init__(self):
        """Initialize stub QA model."""
        self.calls: List[tuple[str, List[RetrievedDoc]]] = []
    
    def generate_answer(self, question: str, docs: List[RetrievedDoc]) -> str:
        """Generate answer (stub implementation).
        
        Args:
            question: The question string.
            docs: List of RetrievedDoc objects.
        
        Returns:
            Simple synthetic answer based on document titles.
        """
        self.calls.append((question, docs))
        if not docs:
            return "I couldn't find any relevant documents."
        titles = ", ".join(d.title for d in docs)
        return f"Answer about: {titles}"


def create_feed_html() -> str:
    """Create a simple feed HTML fixture with two posts.
    
    Returns:
        HTML string containing two blog posts about RAG and GPU topics.
    """
    return """
    <html>
        <body>
            <div class="post">
                <a class="post-link" href="https://developer.nvidia.com/blog/rag-tutorial">NVIDIA RAG Tutorial</a>
                <time datetime="2024-01-15T10:00:00Z">January 15, 2024</time>
            </div>
            <div class="post">
                <a class="post-link" href="https://developer.nvidia.com/blog/gpu-acceleration">GPU Acceleration Basics</a>
                <time datetime="2024-01-16T10:00:00Z">January 16, 2024</time>
            </div>
        </body>
    </html>
    """


@pytest.mark.asyncio
async def test_full_pipeline_smoke():
    """Test the complete end-to-end pipeline from feed HTML to QA evaluation."""
    # Setup feed HTML
    feed_html = create_feed_html()
    
    # Setup state
    state = {}
    
    # Get existing IDs (initially empty)
    existing_ids = get_existing_ids_from_state(state)
    
    # Setup stub dependencies
    html_by_url = {
        "https://developer.nvidia.com/blog/rag-tutorial": "<html><body><article><h1>NVIDIA RAG Tutorial</h1><p>This tutorial covers RAG technology and how to use it with NVIDIA GPUs.</p></article></body></html>",
        "https://developer.nvidia.com/blog/gpu-acceleration": "<html><body><article><h1>GPU Acceleration Basics</h1><p>Learn the fundamentals of GPU acceleration for machine learning workloads.</p></article></body></html>",
    }
    fetcher = StubFetcher(html_by_url)
    summarizer = StubSummarizer()
    rag = InMemoryRag()
    
    # Run ingestion pipeline
    result = await run_ingestion_pipeline(
        feed_html,
        existing_ids=existing_ids,
        fetcher=fetcher,
        summarizer=summarizer,
        rag_client=rag,
    )
    
    # Assertions: Ingestion side
    assert isinstance(result, IngestionResult)
    assert len(result.discovered_posts) == 2
    assert len(result.new_posts) == 2
    assert len(result.raw_contents) == len(result.new_posts)
    assert len(result.summaries) == len(result.raw_contents)
    assert len(rag.summaries) == len(result.summaries)  # All ingested
    
    # Update state
    update_existing_ids_in_state(state, result.new_posts)
    store_last_ingestion_result_metadata(state, result)
    
    # Append to history
    metadata = get_last_ingestion_result_metadata(state)
    append_ingestion_history_entry(state, metadata)
    compact_ingestion_history(state, max_entries=5)
    
    # Assertions: State side
    existing_ids_after = get_existing_ids_from_state(state)
    assert len(existing_ids_after) == 2
    assert all(post.id in existing_ids_after for post in result.new_posts)
    
    stored_metadata = get_last_ingestion_result_metadata(state)
    assert stored_metadata["summaries_count"] == len(result.summaries)
    assert stored_metadata["discovered_count"] == 2
    assert stored_metadata["new_count"] == 2
    
    assert INGESTION_HISTORY_KEY in state
    assert len(state[INGESTION_HISTORY_KEY]) == 1
    
    # Setup QA agent
    qa_model = StubQaModel()
    qa_agent = QAAgent(rag_client=rag, model=qa_model)
    
    # Define evaluation cases
    cases = [
        EvalCase(
            question="What did NVIDIA say about RAG?",
            expected_substrings=["Answer about"],
            max_docs=5,
        ),
        EvalCase(
            question="Tell me about GPU acceleration",
            expected_substrings=["Answer about", "GPU"],
            max_docs=5,
        ),
    ]
    
    # Run evaluation
    results = await run_qa_evaluation(qa_agent, cases)
    summary = summarize_eval_results(results)
    
    # Assertions: QA + eval
    assert len(results) == len(cases)
    assert len(results) == 2
    
    # Check that answers contain expected substrings
    assert all("Answer about" in r.answer for r in results)
    
    # Check that QA model was called
    assert len(qa_model.calls) == 2
    
    # Check evaluation summary
    assert summary.total == 2
    assert summary.passed == 2
    assert summary.failed == 0
    assert summary.pass_rate == 1.0
    
    # Verify that retrieval worked
    assert len(results[0].retrieved_docs) > 0  # Should find RAG-related doc
    assert len(results[1].retrieved_docs) > 0  # Should find GPU-related doc


@pytest.mark.asyncio
async def test_pipeline_with_existing_ids():
    """Test that pipeline correctly filters out existing posts."""
    feed_html = create_feed_html()
    
    # Discover posts first
    from nvidia_blog_agent.agents.workflow import discover_new_posts_from_feed
    discovered, _ = discover_new_posts_from_feed(feed_html, existing_ids=None)
    existing_id = discovered[0].id  # Mark first post as existing
    
    state = {}
    existing_ids = {existing_id}
    
    # Setup stubs
    html_by_url = {
        "https://developer.nvidia.com/blog/gpu-acceleration": "<html><body><article><h1>GPU Acceleration</h1><p>Content</p></article></body></html>",
    }
    fetcher = StubFetcher(html_by_url)
    summarizer = StubSummarizer()
    rag = InMemoryRag()
    
    # Run pipeline
    result = await run_ingestion_pipeline(
        feed_html,
        existing_ids=existing_ids,
        fetcher=fetcher,
        summarizer=summarizer,
        rag_client=rag,
    )
    
    # Should only process the new post
    assert len(result.discovered_posts) == 2
    assert len(result.new_posts) == 1
    assert len(result.summaries) == 1
    assert len(rag.summaries) == 1

