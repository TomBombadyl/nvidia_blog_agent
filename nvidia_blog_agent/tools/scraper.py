"""Scraper tools for fetching and parsing blog post HTML content.

This module provides:
- HtmlFetcher Protocol: Abstract async interface for HTML fetching
- parse_blog_html(): Pure, deterministic HTML parsing into RawBlogContent
- fetch_and_parse_blog(): Orchestrates fetching and parsing via HtmlFetcher

The HtmlFetcher Protocol allows this module to work with various implementations:
- MCP-based HTML fetchers (future)
- HTTP clients (future)
- Test doubles (for testing)
"""

import re
from typing import Protocol, Optional
from bs4 import BeautifulSoup, Tag, NavigableString
from nvidia_blog_agent.contracts.blog_models import BlogPost, RawBlogContent


class HtmlFetcher(Protocol):
    """Protocol for async HTML fetching.
    
    This abstract interface allows the scraper to work with various implementations:
    - MCP-based HTML fetchers
    - HTTP clients
    - Test doubles
    
    Implementations of this protocol must provide an async fetch_html method.
    """
    
    async def fetch_html(self, url: str) -> str:
        """Fetch the HTML content for the given URL.
        
        Args:
            url: The URL to fetch HTML from.
        
        Returns:
            Raw HTML string content.
        
        Raises:
            Implementation-specific exceptions (e.g., HTTP errors, network errors).
        """
        ...


def _select_article_root(soup: BeautifulSoup) -> Optional[Tag]:
    """Select the best root element containing the article content.
    
    Tries multiple strategies in order:
    1. <article> tag
    2. div with class containing "post", "article", "blog", "content"
    3. <main> tag
    4. <body> tag as fallback
    
    Args:
        soup: BeautifulSoup object representing the HTML document.
    
    Returns:
        Tag element containing the article, or None if not found.
    """
    # Strategy 1: Look for <article> tag
    article = soup.find("article")
    if article:
        return article
    
    # Strategy 2: Look for common container classes
    container_classes = ["post", "article", "blog-article", "blog-post", "content", "main-content"]
    for class_name in container_classes:
        container = soup.find("div", class_=re.compile(class_name, re.I))
        if container:
            return container
    
    # Strategy 3: Look for <main> tag
    main = soup.find("main")
    if main:
        return main
    
    # Strategy 4: Fallback to body
    body = soup.find("body")
    if body:
        return body
    
    return None


def _clean_text(node: Tag) -> str:
    """Extract clean text from a BeautifulSoup node, removing scripts/styles.
    
    Args:
        node: BeautifulSoup Tag node to extract text from.
    
    Returns:
        Clean text content with normalized whitespace.
    """
    # Create a copy to avoid modifying the original
    node_copy = BeautifulSoup(str(node), "html.parser")
    
    # Remove script and style elements
    for element in node_copy.find_all(["script", "style", "noscript"]):
        element.decompose()
    
    # Get text and normalize whitespace
    text = node_copy.get_text(separator=" ", strip=True)
    
    # Collapse multiple spaces/newlines into single spaces
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def _extract_sections(root: Tag) -> list[str]:
    """Extract logical sections from HTML based on headings.
    
    For each heading (h1-h6), creates a section containing:
    - The heading text
    - The subsequent paragraph(s) up to the next heading
    
    Args:
        root: BeautifulSoup Tag element containing the article content.
    
    Returns:
        List of section strings, ordered by document position.
    """
    sections = []
    current_section = []
    current_heading = None
    
    # Find all headings and paragraphs
    elements = root.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p"])
    
    for elem in elements:
        if elem.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            # Save previous section if it exists
            if current_heading and current_section:
                section_text = f"{current_heading}\n\n" + "\n\n".join(current_section)
                sections.append(section_text.strip())
            
            # Start new section
            current_heading = elem.get_text(strip=True)
            current_section = []
        elif elem.name == "p" and current_heading:
            # Add paragraph to current section
            para_text = elem.get_text(strip=True)
            if para_text:
                current_section.append(para_text)
    
    # Don't forget the last section
    if current_heading and current_section:
        section_text = f"{current_heading}\n\n" + "\n\n".join(current_section)
        sections.append(section_text.strip())
    
    # If no sections were found, return empty list
    # (The full text will still be in RawBlogContent.text)
    return sections


def parse_blog_html(blog: BlogPost, html: str) -> RawBlogContent:
    """Parse HTML content into a RawBlogContent object.
    
    This function extracts:
    - Raw HTML (preserved as-is)
    - Clean text content (main article text)
    - Logical sections (based on headings)
    
    The parser is robust to various HTML structures:
    - Prefers <article> tag
    - Falls back to common container classes (div.post, etc.)
    - Handles missing structure gracefully
    
    Args:
        blog: BlogPost object containing metadata (url, title, etc.).
        html: Raw HTML string to parse.
    
    Returns:
        RawBlogContent object with parsed content.
    
    Example:
        >>> blog = BlogPost(
        ...     id="test-id",
        ...     url="https://example.com/post",
        ...     title="Test Post"
        ... )
        >>> html = "<article><h1>Title</h1><p>Content</p></article>"
        >>> content = parse_blog_html(blog, html)
        >>> content.title
        'Test Post'
        >>> len(content.text) > 0
        True
    """
    if not html or not html.strip():
        # Return minimal RawBlogContent if HTML is empty
        # Use title as placeholder text since text field cannot be empty
        placeholder_text = blog.title if blog.title else "No content available"
        return RawBlogContent(
            blog_id=blog.id,
            url=blog.url,
            title=blog.title,
            html=html,
            text=placeholder_text,
            sections=[]
        )
    
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        # If parsing fails, return minimal content
        # Use title as placeholder text since text field cannot be empty
        placeholder_text = blog.title if blog.title else "No content available"
        return RawBlogContent(
            blog_id=blog.id,
            url=blog.url,
            title=blog.title,
            html=html,
            text=placeholder_text,
            sections=[]
        )
    
    # Find the article root
    root = _select_article_root(soup)
    
    if not root:
        # If no root found, use entire soup
        root = soup
    
    # Extract clean text
    text = _clean_text(root)
    
    # Extract sections
    sections = _extract_sections(root)
    
    # If no sections were found but we have text, create a single section
    # (This handles the case where there are no headings)
    if not sections and text:
        sections = [text]
    
    return RawBlogContent(
        blog_id=blog.id,
        url=blog.url,
        title=blog.title,
        html=html,
        text=text,
        sections=sections
    )


async def fetch_and_parse_blog(
    blog: BlogPost,
    fetcher: HtmlFetcher
) -> RawBlogContent:
    """Fetch HTML for a blog post and parse it into RawBlogContent.
    
    This function orchestrates the fetching and parsing process:
    1. Calls the HtmlFetcher to fetch HTML
    2. Parses the HTML using parse_blog_html()
    
    Args:
        blog: BlogPost object containing the URL and metadata.
        fetcher: HtmlFetcher implementation to use for fetching HTML.
    
    Returns:
        RawBlogContent object with fetched and parsed content.
    
    Example:
        >>> class FakeFetcher:
        ...     async def fetch_html(self, url: str) -> str:
        ...         return "<html><body>Content</body></html>"
        >>> blog = BlogPost(
        ...     id="test-id",
        ...     url="https://example.com/post",
        ...     title="Test"
        ... )
        >>> content = await fetch_and_parse_blog(blog, FakeFetcher())
        >>> content.blog_id
        'test-id'
    """
    # Fetch HTML using the fetcher
    html = await fetcher.fetch_html(str(blog.url))
    
    # Parse the HTML
    return parse_blog_html(blog, html)

