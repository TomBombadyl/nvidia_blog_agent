"""Unit tests for discovery tools.

Tests cover:
- diff_new_posts filtering logic
- discover_posts_from_feed HTML parsing
- Edge cases and malformed input handling
- Deterministic ID generation
"""

import pytest
from datetime import datetime
from nvidia_blog_agent.tools.discovery import (
    diff_new_posts,
    discover_posts_from_feed,
)
from nvidia_blog_agent.contracts.blog_models import BlogPost, generate_post_id


class TestDiffNewPosts:
    """Tests for diff_new_posts function."""

    def test_empty_existing_ids_returns_all(self):
        """Test that empty existing_ids returns all discovered posts."""
        posts = [
            BlogPost(
                id="id1",
                url="https://developer.nvidia.com/blog/post-1",
                title="Post 1"
            ),
            BlogPost(
                id="id2",
                url="https://developer.nvidia.com/blog/post-2",
                title="Post 2"
            ),
        ]
        
        result = diff_new_posts([], posts)
        assert len(result) == 2
        assert result[0].id == "id1"
        assert result[1].id == "id2"

    def test_some_overlap_filters_correctly(self):
        """Test that only truly new posts are returned when there's overlap."""
        posts = [
            BlogPost(
                id="id1",
                url="https://developer.nvidia.com/blog/post-1",
                title="Post 1"
            ),
            BlogPost(
                id="id2",
                url="https://developer.nvidia.com/blog/post-2",
                title="Post 2"
            ),
            BlogPost(
                id="id3",
                url="https://developer.nvidia.com/blog/post-3",
                title="Post 3"
            ),
        ]
        
        existing_ids = ["id1", "id3"]
        result = diff_new_posts(existing_ids, posts)
        
        assert len(result) == 1
        assert result[0].id == "id2"
        assert result[0].title == "Post 2"

    def test_all_exist_returns_empty(self):
        """Test that when all posts exist, an empty list is returned."""
        posts = [
            BlogPost(
                id="id1",
                url="https://developer.nvidia.com/blog/post-1",
                title="Post 1"
            ),
            BlogPost(
                id="id2",
                url="https://developer.nvidia.com/blog/post-2",
                title="Post 2"
            ),
        ]
        
        existing_ids = ["id1", "id2"]
        result = diff_new_posts(existing_ids, posts)
        
        assert len(result) == 0

    def test_preserves_order(self):
        """Test that the original order from discovered_posts is preserved."""
        posts = [
            BlogPost(id="id1", url="https://example.com/1", title="First"),
            BlogPost(id="id2", url="https://example.com/2", title="Second"),
            BlogPost(id="id3", url="https://example.com/3", title="Third"),
            BlogPost(id="id4", url="https://example.com/4", title="Fourth"),
        ]
        
        existing_ids = ["id2", "id4"]
        result = diff_new_posts(existing_ids, posts)
        
        assert len(result) == 2
        assert result[0].id == "id1"
        assert result[0].title == "First"
        assert result[1].id == "id3"
        assert result[1].title == "Third"

    def test_with_set_input(self):
        """Test that existing_ids can be a set."""
        posts = [
            BlogPost(id="id1", url="https://example.com/1", title="Post 1"),
            BlogPost(id="id2", url="https://example.com/2", title="Post 2"),
        ]
        
        existing_ids = {"id1"}
        result = diff_new_posts(existing_ids, posts)
        
        assert len(result) == 1
        assert result[0].id == "id2"

    def test_empty_discovered_returns_empty(self):
        """Test that empty discovered_posts returns empty list."""
        result = diff_new_posts(["id1"], [])
        assert len(result) == 0


class TestDiscoverPostsFromFeed:
    """Tests for discover_posts_from_feed function."""

    def test_simple_feed_with_two_posts(self):
        """Test parsing a feed with two valid posts."""
        html = '''
        <div class="post">
            <a class="post-link" href="https://developer.nvidia.com/blog/post-1">First Post</a>
            <time datetime="2025-01-02">Jan 2, 2025</time>
        </div>
        <div class="post">
            <a class="post-link" href="https://developer.nvidia.com/blog/post-2">Second Post</a>
            <time datetime="2025-01-03">Jan 3, 2025</time>
        </div>
        '''
        
        posts = discover_posts_from_feed(html)
        
        assert len(posts) == 2
        assert posts[0].title == "First Post"
        assert str(posts[0].url) == "https://developer.nvidia.com/blog/post-1"
        assert posts[0].published_at == datetime(2025, 1, 2)
        assert posts[0].source == "nvidia_tech_blog"
        
        assert posts[1].title == "Second Post"
        assert str(posts[1].url) == "https://developer.nvidia.com/blog/post-2"
        assert posts[1].published_at == datetime(2025, 1, 3)

    def test_ids_are_stable_and_deterministic(self):
        """Test that IDs are generated deterministically using generate_post_id."""
        html = '''
        <div class="post">
            <a class="post-link" href="https://developer.nvidia.com/blog/same-post">Same Post</a>
        </div>
        '''
        
        posts1 = discover_posts_from_feed(html)
        posts2 = discover_posts_from_feed(html)
        
        assert len(posts1) == 1
        assert len(posts2) == 1
        assert posts1[0].id == posts2[0].id
        
        # Verify ID matches what generate_post_id would produce
        expected_id = generate_post_id("https://developer.nvidia.com/blog/same-post")
        assert posts1[0].id == expected_id

    def test_malformed_post_is_skipped(self):
        """Test that malformed posts (missing link or title) are skipped."""
        html = '''
        <div class="post">
            <a class="post-link" href="https://developer.nvidia.com/blog/valid">Valid Post</a>
        </div>
        <div class="post">
            <!-- Missing link -->
            <span>Invalid Post</span>
        </div>
        <div class="post">
            <a class="post-link" href="https://developer.nvidia.com/blog/empty-title"></a>
        </div>
        '''
        
        posts = discover_posts_from_feed(html)
        
        # Only the valid post should be returned
        assert len(posts) == 1
        assert posts[0].title == "Valid Post"

    def test_whitespace_is_trimmed_from_titles(self):
        """Test that leading/trailing whitespace is trimmed from titles."""
        html = '''
        <div class="post">
            <a class="post-link" href="https://developer.nvidia.com/blog/post">   Trimmed Title   </a>
        </div>
        '''
        
        posts = discover_posts_from_feed(html)
        
        assert len(posts) == 1
        assert posts[0].title == "Trimmed Title"
        assert posts[0].title == posts[0].title.strip()

    def test_published_at_optional(self):
        """Test that published_at can be None if datetime is not present."""
        html = '''
        <div class="post">
            <a class="post-link" href="https://developer.nvidia.com/blog/post">Post Without Date</a>
        </div>
        '''
        
        posts = discover_posts_from_feed(html)
        
        assert len(posts) == 1
        assert posts[0].published_at is None

    def test_custom_source(self):
        """Test that custom source can be specified."""
        html = '''
        <div class="post">
            <a class="post-link" href="https://developer.nvidia.com/blog/post">Post</a>
        </div>
        '''
        
        posts = discover_posts_from_feed(html, default_source="custom_source")
        
        assert len(posts) == 1
        assert posts[0].source == "custom_source"

    def test_empty_feed_returns_empty_list(self):
        """Test that empty or whitespace-only feed returns empty list."""
        assert discover_posts_from_feed("") == []
        assert discover_posts_from_feed("   ") == []
        assert discover_posts_from_feed("\n\n") == []

    def test_feed_without_post_containers(self):
        """Test that feed without expected structure returns empty list."""
        html = "<html><body><p>No posts here</p></body></html>"
        posts = discover_posts_from_feed(html)
        assert len(posts) == 0

    def test_datetime_parsing_variations(self):
        """Test parsing different datetime formats."""
        html = '''
        <div class="post">
            <a class="post-link" href="https://developer.nvidia.com/blog/post1">Post 1</a>
            <time datetime="2025-01-02">Jan 2</time>
        </div>
        <div class="post">
            <a class="post-link" href="https://developer.nvidia.com/blog/post2">Post 2</a>
            <time datetime="2025-01-02T10:30:00">Jan 2, 10:30</time>
        </div>
        <div class="post">
            <a class="post-link" href="https://developer.nvidia.com/blog/post3">Post 3</a>
            <time datetime="invalid-date">Invalid</time>
        </div>
        '''
        
        posts = discover_posts_from_feed(html)
        
        assert len(posts) == 3
        assert posts[0].published_at == datetime(2025, 1, 2)
        assert posts[1].published_at == datetime(2025, 1, 2, 10, 30)
        assert posts[2].published_at is None  # Invalid date should be None

    def test_fallback_to_any_link(self):
        """Test that parser falls back to any link if post-link class not found."""
        html = '''
        <div class="post">
            <a href="https://developer.nvidia.com/blog/post">Post Without Class</a>
        </div>
        '''
        
        posts = discover_posts_from_feed(html)
        
        assert len(posts) == 1
        assert posts[0].title == "Post Without Class"

    def test_multiple_posts_preserve_order(self):
        """Test that multiple posts maintain their order from the HTML."""
        html = '''
        <div class="post">
            <a class="post-link" href="https://developer.nvidia.com/blog/post-1">First</a>
        </div>
        <div class="post">
            <a class="post-link" href="https://developer.nvidia.com/blog/post-2">Second</a>
        </div>
        <div class="post">
            <a class="post-link" href="https://developer.nvidia.com/blog/post-3">Third</a>
        </div>
        '''
        
        posts = discover_posts_from_feed(html)
        
        assert len(posts) == 3
        assert posts[0].title == "First"
        assert posts[1].title == "Second"
        assert posts[2].title == "Third"

    def test_tags_extraction(self):
        """Test that tags are extracted if present."""
        html = '''
        <div class="post">
            <a class="post-link" href="https://developer.nvidia.com/blog/post">Post</a>
            <span class="tag">AI</span>
            <span class="tag">CUDA</span>
        </div>
        '''
        
        posts = discover_posts_from_feed(html)
        
        assert len(posts) == 1
        assert "AI" in posts[0].tags
        assert "CUDA" in posts[0].tags

    def test_invalid_html_does_not_raise(self):
        """Test that invalid HTML doesn't raise exceptions."""
        # Malformed HTML should be handled gracefully
        html = "<div><unclosed><tag>"
        posts = discover_posts_from_feed(html)
        # Should return empty list or handle gracefully
        assert isinstance(posts, list)

    def test_article_tags_as_fallback(self):
        """Test that article tags are used as fallback containers."""
        html = '''
        <article>
            <a class="post-link" href="https://developer.nvidia.com/blog/post">Article Post</a>
        </article>
        '''
        
        posts = discover_posts_from_feed(html)
        
        assert len(posts) == 1
        assert posts[0].title == "Article Post"

