"""Tests for parallel scraping functionality in the workflow.

Tests cover:
- Concurrent fetching of multiple blog posts
- Order preservation
- Empty posts list handling
- Integration with HtmlFetcher
"""

import pytest
from nvidia_blog_agent.contracts.blog_models import BlogPost
from nvidia_blog_agent.tools.scraper import HtmlFetcher
from nvidia_blog_agent.agents.workflow import fetch_raw_contents_for_posts


class StubFetcher:
    """Stub implementation of HtmlFetcher for testing parallel behavior."""
    
    def __init__(self, html_by_url: dict[str, str]):
        """Initialize stub with HTML content mapped by URL.
        
        Args:
            html_by_url: Dictionary mapping URL strings to HTML content strings.
        """
        self.html_by_url = html_by_url
        self.called_urls: list[str] = []
    
    async def fetch_html(self, url: str) -> str:
        """Fetch HTML for a URL (stub implementation).
        
        Args:
            url: URL to fetch HTML for.
        
        Returns:
            HTML content from html_by_url dictionary.
        """
        self.called_urls.append(url)
        return self.html_by_url[url]


class TestFetchRawContentsForPosts:
    """Tests for fetch_raw_contents_for_posts parallel scraping."""
    
    @pytest.mark.asyncio
    async def test_multiple_posts_processed_concurrently(self):
        """Test that multiple posts are processed concurrently."""
        posts = [
            BlogPost(
                id="id1",
                url="https://developer.nvidia.com/blog/post1",
                title="Post 1",
            ),
            BlogPost(
                id="id2",
                url="https://developer.nvidia.com/blog/post2",
                title="Post 2",
            ),
            BlogPost(
                id="id3",
                url="https://developer.nvidia.com/blog/post3",
                title="Post 3",
            ),
        ]
        
        html_by_url = {
            "https://developer.nvidia.com/blog/post1": "<html><body><article><h1>Post 1</h1><p>Content 1</p></article></body></html>",
            "https://developer.nvidia.com/blog/post2": "<html><body><article><h1>Post 2</h1><p>Content 2</p></article></body></html>",
            "https://developer.nvidia.com/blog/post3": "<html><body><article><h1>Post 3</h1><p>Content 3</p></article></body></html>",
        }
        
        fetcher = StubFetcher(html_by_url)
        
        result = await fetch_raw_contents_for_posts(posts, fetcher)
        
        # Verify all posts were processed
        assert len(result) == 3
        
        # Verify fetcher was called for all URLs
        assert len(fetcher.called_urls) == 3
        assert "https://developer.nvidia.com/blog/post1" in fetcher.called_urls
        assert "https://developer.nvidia.com/blog/post2" in fetcher.called_urls
        assert "https://developer.nvidia.com/blog/post3" in fetcher.called_urls
        
        # Verify each RawBlogContent matches its BlogPost
        assert result[0].blog_id == "id1"
        assert result[0].title == "Post 1"
        assert str(result[0].url) == "https://developer.nvidia.com/blog/post1"
        
        assert result[1].blog_id == "id2"
        assert result[1].title == "Post 2"
        assert str(result[1].url) == "https://developer.nvidia.com/blog/post2"
        
        assert result[2].blog_id == "id3"
        assert result[2].title == "Post 3"
        assert str(result[2].url) == "https://developer.nvidia.com/blog/post3"
        
        # Verify HTML and text are non-empty
        assert len(result[0].html) > 0
        assert len(result[0].text) > 0
        assert len(result[1].html) > 0
        assert len(result[1].text) > 0
        assert len(result[2].html) > 0
        assert len(result[2].text) > 0
    
    @pytest.mark.asyncio
    async def test_order_preservation(self):
        """Test that results preserve the order of input posts."""
        posts = [
            BlogPost(id="id1", url="https://example.com/1", title="First"),
            BlogPost(id="id2", url="https://example.com/2", title="Second"),
            BlogPost(id="id3", url="https://example.com/3", title="Third"),
        ]
        
        html_by_url = {
            "https://example.com/1": "<html><body><article><h1>First</h1><p>Content</p></article></body></html>",
            "https://example.com/2": "<html><body><article><h1>Second</h1><p>Content</p></article></body></html>",
            "https://example.com/3": "<html><body><article><h1>Third</h1><p>Content</p></article></body></html>",
        }
        
        fetcher = StubFetcher(html_by_url)
        
        result = await fetch_raw_contents_for_posts(posts, fetcher)
        
        # Verify order is preserved
        assert result[0].blog_id == "id1"
        assert result[0].title == "First"
        assert result[1].blog_id == "id2"
        assert result[1].title == "Second"
        assert result[2].blog_id == "id3"
        assert result[2].title == "Third"
    
    @pytest.mark.asyncio
    async def test_empty_posts_list(self):
        """Test that empty posts list returns empty list without calling fetcher."""
        fetcher = StubFetcher({})
        
        result = await fetch_raw_contents_for_posts([], fetcher)
        
        assert result == []
        assert len(fetcher.called_urls) == 0
    
    @pytest.mark.asyncio
    async def test_single_post(self):
        """Test processing a single post."""
        posts = [
            BlogPost(
                id="id1",
                url="https://developer.nvidia.com/blog/single",
                title="Single Post",
            ),
        ]
        
        html_by_url = {
            "https://developer.nvidia.com/blog/single": "<html><body><article><h1>Single</h1><p>Content</p></article></body></html>",
        }
        
        fetcher = StubFetcher(html_by_url)
        
        result = await fetch_raw_contents_for_posts(posts, fetcher)
        
        assert len(result) == 1
        assert result[0].blog_id == "id1"
        assert result[0].title == "Single Post"
        assert len(fetcher.called_urls) == 1
        assert "https://developer.nvidia.com/blog/single" in fetcher.called_urls
    
    @pytest.mark.asyncio
    async def test_five_posts(self):
        """Test processing five posts to verify scalability."""
        posts = [
            BlogPost(id=f"id{i}", url=f"https://example.com/{i}", title=f"Post {i}")
            for i in range(1, 6)
        ]
        
        html_by_url = {
            f"https://example.com/{i}": f"<html><body><article><h1>Post {i}</h1><p>Content {i}</p></article></body></html>"
            for i in range(1, 6)
        }
        
        fetcher = StubFetcher(html_by_url)
        
        result = await fetch_raw_contents_for_posts(posts, fetcher)
        
        assert len(result) == 5
        assert len(fetcher.called_urls) == 5
        
        # Verify all posts were processed correctly
        for i, content in enumerate(result, start=1):
            assert content.blog_id == f"id{i}"
            assert content.title == f"Post {i}"
            assert len(content.html) > 0
            assert len(content.text) > 0

