"""HTTP-based HTML fetcher implementation.

This module provides HttpHtmlFetcher, a concrete implementation of the
HtmlFetcher protocol that uses httpx to fetch HTML content from URLs.
It also provides a helper function to fetch the NVIDIA Tech Blog feed.
"""

import httpx
from typing import Protocol
from nvidia_blog_agent.tools.scraper import HtmlFetcher
from nvidia_blog_agent.retry import retry_with_backoff


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
        
        # Set browser-like headers to avoid bot detection
        # These mimic a real Chrome browser on Windows
        default_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
        
        # Merge user-provided headers with defaults (user headers take precedence)
        for key, value in default_headers.items():
            if key not in self.headers:
                self.headers[key] = value
    
    async def fetch_html(self, url: str, referer: str | None = None) -> str:
        """Fetch HTML content from the given URL.
        
        Args:
            url: The URL to fetch HTML from.
            referer: Optional referer URL to include in headers (for browser-like behavior).
        
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
        # Create headers copy and add referer if provided
        request_headers = dict(self.headers)
        if referer:
            request_headers["Referer"] = referer
        
        # Use connection pooling with limits
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=request_headers,
            limits=limits,
            http2=True
        ) as client:
            # Use retry logic for transient failures
            async def _make_request():
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                return response.text
            
            return await retry_with_backoff(
                _make_request,
                max_retries=3,
                initial_delay=1.0,
                max_delay=10.0,
                multiplier=2.0
            )


async def fetch_feed_html(feed_url: str | None = None) -> str:
    """Fetch the NVIDIA Tech Blog feed.
    
    Fetches the feed content (RSS/Atom XML or HTML) from the NVIDIA Developer Blog.
    The default URL is the RSS/Atom feed which is more reliable and less likely
    to be blocked than the HTML index page.
    
    Args:
        feed_url: Optional custom feed URL. If None, uses the default NVIDIA
                 Tech Blog RSS feed: https://developer.nvidia.com/blog/feed/
    
    Returns:
        Raw XML/HTML string containing the blog feed (Atom/RSS XML or HTML).
    
    Raises:
        httpx.HTTPStatusError: If the HTTP request returns a non-2xx status code.
        httpx.RequestError: If the request fails due to network or other errors.
    
    Example:
        >>> feed = await fetch_feed_html()
        >>> len(feed) > 0
        True
        >>> # Use custom URL
        >>> feed = await fetch_feed_html("https://custom-blog.com/feed/")
    """
    if feed_url is None:
        # Use RSS/Atom feed by default (more reliable, less likely to be blocked)
        feed_url = "https://developer.nvidia.com/blog/feed/"
    
    fetcher = HttpHtmlFetcher()
    return await fetcher.fetch_html(feed_url)

