"""Unit tests for scraper tools.

Tests cover:
- parse_blog_html with various HTML structures
- fetch_and_parse_blog with fake fetchers
- Edge cases and malformed HTML handling
"""

import pytest
from nvidia_blog_agent.tools.scraper import (
    parse_blog_html,
    fetch_and_parse_blog,
)
from nvidia_blog_agent.contracts.blog_models import BlogPost


class FakeFetcher:
    """Fake HtmlFetcher implementation for testing."""

    def __init__(self, html: str):
        """Initialize with HTML to return.

        Args:
            html: HTML string to return when fetch_html is called.
        """
        self.html = html
        self.called_urls: list[str] = []

    async def fetch_html(self, url: str) -> str:
        """Fake fetch_html that records the URL and returns preset HTML.

        Args:
            url: URL that was requested.

        Returns:
            The HTML string provided during initialization.
        """
        self.called_urls.append(url)
        return self.html


class TestParseBlogHtml:
    """Tests for parse_blog_html function."""

    def test_basic_article_structure(self):
        """Test parsing HTML with standard article structure."""
        blog = BlogPost(
            id="test-id",
            url="https://developer.nvidia.com/blog/test",
            title="Test Blog Post",
        )

        html = """
        <html>
        <body>
            <article>
                <h1>Article Title</h1>
                <p>Intro paragraph with some content.</p>
                <h2>Section 1</h2>
                <p>Section 1 body text goes here.</p>
                <p>More content in section 1.</p>
                <h2>Section 2</h2>
                <p>Section 2 body text.</p>
            </article>
        </body>
        </html>
        """

        content = parse_blog_html(blog, html)

        # Verify basic fields
        assert content.blog_id == "test-id"
        assert str(content.url) == "https://developer.nvidia.com/blog/test"
        assert content.title == "Test Blog Post"
        # HTML may be normalized by BeautifulSoup, so just verify it contains key elements
        assert "<article>" in content.html or "Article Title" in content.html

        # Verify text extraction
        assert "Intro paragraph" in content.text
        assert "Section 1 body text" in content.text
        assert "Section 2 body text" in content.text

        # Verify sections extraction
        assert len(content.sections) >= 2
        assert any("Section 1" in section for section in content.sections)
        assert any("Section 2" in section for section in content.sections)

    def test_missing_article_fallback(self):
        """Test parsing HTML without <article> tag, using fallback containers."""
        blog = BlogPost(
            id="test-id",
            url="https://developer.nvidia.com/blog/test",
            title="Test Post",
        )

        html = """
        <html>
        <body>
            <div class="post">
                <h1>Post Title</h1>
                <p>Post content goes here.</p>
                <h2>Subsection</h2>
                <p>Subsection content.</p>
            </div>
        </body>
        </html>
        """

        content = parse_blog_html(blog, html)

        # Should still extract content
        assert len(content.text) > 0
        assert "Post content" in content.text
        assert len(content.sections) > 0

    def test_no_headings(self):
        """Test parsing HTML with only paragraphs, no headings."""
        blog = BlogPost(
            id="test-id",
            url="https://developer.nvidia.com/blog/test",
            title="Test Post",
        )

        html = """
        <html>
        <body>
            <article>
                <p>First paragraph with some content.</p>
                <p>Second paragraph with more content.</p>
                <p>Third paragraph continues the discussion.</p>
            </article>
        </body>
        </html>
        """

        content = parse_blog_html(blog, html)

        # Text should be populated
        assert len(content.text) > 0
        assert "First paragraph" in content.text
        assert "Second paragraph" in content.text

        # Sections should either be empty or contain full text
        # (Implementation may create a single section with all text)
        assert isinstance(content.sections, list)
        if content.sections:
            # If sections exist, they should contain the text
            assert any("First paragraph" in section for section in content.sections)

    def test_script_style_stripping(self):
        """Test that script and style tags are removed from text."""
        blog = BlogPost(
            id="test-id",
            url="https://developer.nvidia.com/blog/test",
            title="Test Post",
        )

        html = """
        <html>
        <body>
            <article>
                <h1>Article Title</h1>
                <p>This is the actual content.</p>
                <script>
                    console.log("This should not appear");
                    var x = 123;
                </script>
                <style>
                    body { color: red; }
                    .post { margin: 10px; }
                </style>
                <p>More content after scripts.</p>
            </article>
        </body>
        </html>
        """

        content = parse_blog_html(blog, html)

        # Script content should not be in text
        assert "console.log" not in content.text
        assert "var x = 123" not in content.text

        # Style content should not be in text
        assert "body { color: red; }" not in content.text
        assert ".post { margin: 10px; }" not in content.text

        # Actual content should be present
        assert "This is the actual content" in content.text
        assert "More content after scripts" in content.text

    def test_multiple_heading_levels(self):
        """Test parsing with h1, h2, h3 headings."""
        blog = BlogPost(
            id="test-id",
            url="https://developer.nvidia.com/blog/test",
            title="Test Post",
        )

        html = """
        <html>
        <body>
            <article>
                <h1>Main Title</h1>
                <p>Introduction.</p>
                <h2>Section A</h2>
                <p>Section A content.</p>
                <h3>Subsection A.1</h3>
                <p>Subsection content.</p>
                <h2>Section B</h2>
                <p>Section B content.</p>
            </article>
        </body>
        </html>
        """

        content = parse_blog_html(blog, html)

        # Should extract multiple sections
        assert len(content.sections) >= 2
        assert any("Section A" in section for section in content.sections)
        assert any("Section B" in section for section in content.sections)

    def test_empty_html(self):
        """Test handling of empty HTML."""
        blog = BlogPost(
            id="test-id",
            url="https://developer.nvidia.com/blog/test",
            title="Test Post",
        )

        content = parse_blog_html(blog, "")

        assert content.html == ""
        # Text field cannot be empty per RawBlogContent validation,
        # so it should use title as placeholder
        assert content.text == "Test Post"
        assert content.sections == []

    def test_whitespace_normalization(self):
        """Test that whitespace is normalized in extracted text."""
        blog = BlogPost(
            id="test-id",
            url="https://developer.nvidia.com/blog/test",
            title="Test Post",
        )

        html = """
        <article>
            <p>Paragraph    with    multiple    spaces.</p>
            <p>Paragraph


            with


            newlines.</p>
        </article>
        """

        content = parse_blog_html(blog, html)

        # Should not have excessive whitespace
        assert "    " not in content.text  # No multiple spaces
        assert "\n\n\n" not in content.text  # No multiple newlines

    def test_fallback_to_body(self):
        """Test that parser falls back to body if no article/container found."""
        blog = BlogPost(
            id="test-id",
            url="https://developer.nvidia.com/blog/test",
            title="Test Post",
        )

        html = """
        <html>
        <body>
            <h1>Title</h1>
            <p>Body content without article tag.</p>
        </body>
        </html>
        """

        content = parse_blog_html(blog, html)

        # Should still extract content from body
        assert len(content.text) > 0
        assert "Body content" in content.text

    def test_div_with_content_class(self):
        """Test parsing div with 'content' class as fallback."""
        blog = BlogPost(
            id="test-id",
            url="https://developer.nvidia.com/blog/test",
            title="Test Post",
        )

        html = """
        <html>
        <body>
            <div class="content">
                <h1>Content Title</h1>
                <p>Content paragraph.</p>
            </div>
        </body>
        </html>
        """

        content = parse_blog_html(blog, html)

        assert "Content paragraph" in content.text
        assert len(content.sections) > 0

    def test_main_tag_fallback(self):
        """Test parsing <main> tag as fallback."""
        blog = BlogPost(
            id="test-id",
            url="https://developer.nvidia.com/blog/test",
            title="Test Post",
        )

        html = """
        <html>
        <body>
            <main>
                <h1>Main Content</h1>
                <p>Content in main tag.</p>
            </main>
        </body>
        </html>
        """

        content = parse_blog_html(blog, html)

        assert "Content in main tag" in content.text


class TestFetchAndParseBlog:
    """Tests for fetch_and_parse_blog function."""

    @pytest.mark.asyncio
    async def test_fetch_and_parse_basic(self):
        """Test basic fetch and parse workflow."""
        blog = BlogPost(
            id="test-id",
            url="https://developer.nvidia.com/blog/test",
            title="Test Blog Post",
        )

        html = """
        <html>
        <body>
            <article>
                <h1>Article Title</h1>
                <p>Article content goes here.</p>
            </article>
        </body>
        </html>
        """

        fetcher = FakeFetcher(html)
        content = await fetch_and_parse_blog(blog, fetcher)

        # Verify fetcher was called with correct URL
        assert len(fetcher.called_urls) == 1
        assert fetcher.called_urls[0] == "https://developer.nvidia.com/blog/test"

        # Verify content was parsed correctly
        assert content.blog_id == "test-id"
        assert content.title == "Test Blog Post"
        assert "Article content" in content.text

    @pytest.mark.asyncio
    async def test_fetch_and_parse_with_sections(self):
        """Test fetch and parse with sections."""
        blog = BlogPost(
            id="test-id",
            url="https://developer.nvidia.com/blog/test",
            title="Test Post",
        )

        html = """
        <article>
            <h1>Title</h1>
            <p>Intro.</p>
            <h2>Section 1</h2>
            <p>Section 1 content.</p>
            <h2>Section 2</h2>
            <p>Section 2 content.</p>
        </article>
        """

        fetcher = FakeFetcher(html)
        content = await fetch_and_parse_blog(blog, fetcher)

        # Verify sections were extracted
        assert len(content.sections) >= 2
        assert any("Section 1" in section for section in content.sections)
        assert any("Section 2" in section for section in content.sections)

    @pytest.mark.asyncio
    async def test_fetch_and_parse_empty_html(self):
        """Test fetch and parse with empty HTML."""
        blog = BlogPost(
            id="test-id",
            url="https://developer.nvidia.com/blog/test",
            title="Test Post",
        )

        fetcher = FakeFetcher("")
        content = await fetch_and_parse_blog(blog, fetcher)

        # Text field cannot be empty per RawBlogContent validation,
        # so it should use title as placeholder
        assert content.text == "Test Post"
        assert content.sections == []

    @pytest.mark.asyncio
    async def test_fetch_and_parse_preserves_html(self):
        """Test that raw HTML is preserved in RawBlogContent."""
        blog = BlogPost(
            id="test-id",
            url="https://developer.nvidia.com/blog/test",
            title="Test Post",
        )

        html = "<article><h1>Test</h1><p>Content</p></article>"
        fetcher = FakeFetcher(html)
        content = await fetch_and_parse_blog(blog, fetcher)

        assert content.html == html

    @pytest.mark.asyncio
    async def test_uses_feed_content_when_available(self):
        """Test that feed content is used directly instead of fetching."""
        # BlogPost with content from RSS feed
        feed_content = (
            "<article><h1>Feed Title</h1><p>Content from RSS feed</p></article>"
        )
        blog = BlogPost(
            id="test-id",
            url="https://developer.nvidia.com/blog/test",
            title="Test Post",
            content=feed_content,
        )

        # Fetcher should NOT be called when content is available
        fetcher = FakeFetcher("This should not be used")
        content = await fetch_and_parse_blog(blog, fetcher)

        # Verify fetcher was NOT called
        assert len(fetcher.called_urls) == 0

        # Verify content from feed was used
        assert content.html == feed_content
        assert "Content from RSS feed" in content.text

    @pytest.mark.asyncio
    async def test_fetches_when_content_not_available(self):
        """Test that fetcher is called when blog.content is None."""
        blog = BlogPost(
            id="test-id",
            url="https://developer.nvidia.com/blog/test",
            title="Test Post",
            content=None,  # No feed content
        )

        html = "<article><h1>Fetched Title</h1><p>Fetched content</p></article>"
        fetcher = FakeFetcher(html)
        content = await fetch_and_parse_blog(blog, fetcher)

        # Verify fetcher WAS called
        assert len(fetcher.called_urls) == 1
        assert fetcher.called_urls[0] == "https://developer.nvidia.com/blog/test"

        # Verify fetched content was used
        assert content.html == html
        assert "Fetched content" in content.text
