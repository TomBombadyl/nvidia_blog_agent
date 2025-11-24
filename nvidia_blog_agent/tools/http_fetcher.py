"""HTTP-based HTML fetcher implementation.

This module provides HttpHtmlFetcher, a concrete implementation of the
HtmlFetcher protocol that uses httpx to fetch HTML content from URLs.
It also provides a helper function to fetch the NVIDIA Tech Blog feed.
"""

import httpx
from typing import Protocol
from nvidia_blog_agent.tools.scraper import HtmlFetcher


class HttpHtmlFetcher:
    """HTTP-based implementation of HtmlFetcher protocol.
    
    Uses httpx.AsyncClient to fetch HTML content from URLs with configurable
    timeout and error handling.
    
    Attributes:
        timeout: Request timeout in seconds. Defaults to 30.0.
        headers: Optional custom headers to include in requests.
    """
    
    def __init__(self, timeout: float = 30.0, headers: dict[str, str] | None = None):
        """Initialize HttpHtmlFetcher.
        
        Args:
            timeout: Request timeout in seconds. Defaults to 30.0.
            headers: Optional dictionary of HTTP headers to include in requests.
        """
        self.timeout = timeout
        self.headers = headers or {}
        # Add a default User-Agent if not provided
        if "User-Agent" not in self.headers:
            self.headers["User-Agent"] = (
                "Mozilla/5.0 (compatible; NVIDIA-Blog-Agent/1.0; "
                "+https://github.com/nvidia/blog-agent)"
            )
    
    async def fetch_html(self, url: str) -> str:
        """Fetch HTML content from the given URL.
        
        Args:
            url: The URL to fetch HTML from.
        
        Returns:
            Raw HTML string content.
        
        Raises:
            httpx.HTTPStatusError: If the HTTP request returns a non-2xx status code.
            httpx.RequestError: If the request fails due to network or other errors.
        
        Example:
            >>> fetcher = HttpHtmlFetcher()
            >>> html = await fetcher.fetch_html("https://example.com")
            >>> len(html) > 0
            True
        """
        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            return response.text


async def fetch_feed_html(feed_url: str | None = None) -> str:
    """Fetch the NVIDIA Tech Blog feed HTML.
    
    Fetches the HTML content from the NVIDIA Developer Blog feed page.
    The default URL is the main blog index page which lists recent posts.
    
    Args:
        feed_url: Optional custom feed URL. If None, uses the default NVIDIA
                 Tech Blog URL: https://developer.nvidia.com/blog
    
    Returns:
        Raw HTML string containing the blog feed/index page.
    
    Raises:
        httpx.HTTPStatusError: If the HTTP request returns a non-2xx status code.
        httpx.RequestError: If the request fails due to network or other errors.
    
    Example:
        >>> html = await fetch_feed_html()
        >>> len(html) > 0
        True
        >>> # Use custom URL
        >>> html = await fetch_feed_html("https://custom-blog.com")
    """
    if feed_url is None:
        feed_url = "https://developer.nvidia.com/blog"
    
    fetcher = HttpHtmlFetcher()
    return await fetcher.fetch_html(feed_url)

