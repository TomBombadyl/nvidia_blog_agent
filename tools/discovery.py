"""Discovery tools for finding and tracking NVIDIA tech blog posts.

This module provides pure, deterministic functions for:
- Parsing blog feeds/HTML into BlogPost objects
- Diffing newly discovered posts against previously seen IDs

These tools are designed to be:
- Pure functions (no side effects)
- Deterministic and testable
- Ready for integration with ADK function tools
"""

from datetime import datetime
from typing import List, Optional, Iterable
from bs4 import BeautifulSoup, Tag
from nvidia_blog_agent.contracts.blog_models import BlogPost, generate_post_id


def diff_new_posts(
    existing_ids: Iterable[str],
    discovered_posts: Iterable[BlogPost]
) -> List[BlogPost]:
    """Filter discovered posts to return only those not in existing_ids.
    
    This function efficiently filters out blog posts that have already been
    processed, maintaining the original order of discovered_posts.
    
    Args:
        existing_ids: Iterable of blog post IDs that have already been processed.
                      Can be empty, a list, set, or any iterable.
        discovered_posts: Iterable of BlogPost objects discovered from a feed.
    
    Returns:
        List of BlogPost objects whose IDs are not in existing_ids, in the
        same order as they appeared in discovered_posts.
    
    Example:
        >>> existing = ["id1", "id2"]
        >>> posts = [
        ...     BlogPost(id="id1", url="https://example.com/1", title="Post 1"),
        ...     BlogPost(id="id3", url="https://example.com/3", title="Post 3"),
        ...     BlogPost(id="id2", url="https://example.com/2", title="Post 2"),
        ... ]
        >>> new = diff_new_posts(existing, posts)
        >>> len(new)
        1
        >>> new[0].id
        'id3'
    """
    # Convert to set for O(1) lookup, but preserve order from discovered_posts
    existing_set = set(existing_ids)
    
    # Filter while preserving order
    return [
        post for post in discovered_posts
        if post.id not in existing_set
    ]


def _parse_datetime(value: str) -> Optional[datetime]:
    """Parse a datetime string into a datetime object.
    
    Supports ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS) and common
    variations. Returns None if parsing fails.
    
    Args:
        value: String representation of a datetime.
    
    Returns:
        datetime object if parsing succeeds, None otherwise.
    
    Example:
        >>> _parse_datetime("2025-01-02")
        datetime.datetime(2025, 1, 2, 0, 0)
        >>> _parse_datetime("2025-01-02T10:30:00")
        datetime.datetime(2025, 1, 2, 10, 30)
        >>> _parse_datetime("invalid")
        None
    """
    if not value or not value.strip():
        return None
    
    value = value.strip()
    
    # Try ISO format first (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    
    return None


def _extract_post_from_element(
    element: Tag,
    default_source: str = "nvidia_tech_blog"
) -> Optional[BlogPost]:
    """Extract a BlogPost from a BeautifulSoup element.
    
    Looks for:
    - A link (<a>) with href attribute for URL and text for title
    - A <time> element with datetime attribute for published_at
    - Any tags or categories (optional, not implemented in initial version)
    
    Args:
        element: BeautifulSoup Tag element representing a blog post container.
        default_source: Source identifier to use for the BlogPost.
    
    Returns:
        BlogPost object if extraction succeeds, None if the element is malformed.
    """
    # Find the link element
    link = element.find("a", class_="post-link")
    if not link:
        # Try finding any link as fallback
        link = element.find("a")
    
    if not link or not link.get("href"):
        return None
    
    url_str = link.get("href", "").strip()
    if not url_str:
        return None
    
    # Extract title from link text
    title = link.get_text(strip=True)
    if not title:
        return None
    
    # Try to find published date
    published_at = None
    time_elem = element.find("time")
    if time_elem and time_elem.get("datetime"):
        datetime_str = time_elem.get("datetime")
        published_at = _parse_datetime(datetime_str)
    
    # Generate stable ID from URL
    post_id = generate_post_id(url_str)
    
    # Extract tags if present (for future enhancement)
    tags = []
    tag_elements = element.find_all(class_="tag")
    for tag_elem in tag_elements:
        tag_text = tag_elem.get_text(strip=True)
        if tag_text:
            tags.append(tag_text)
    
    try:
        return BlogPost(
            id=post_id,
            url=url_str,
            title=title,
            published_at=published_at,
            tags=tags,
            source=default_source
        )
    except Exception:
        # If BlogPost validation fails, skip this entry
        return None


def discover_posts_from_feed(
    raw_feed: str,
    *,
    default_source: str = "nvidia_tech_blog"
) -> List[BlogPost]:
    """Parse HTML/XML feed content into a list of BlogPost objects.
    
    This function parses a raw HTML string (representing a blog index page
    or RSS-like content) and extracts blog post entries. It handles:
    - Simple HTML structures with post containers
    - Missing or malformed entries (skips them gracefully)
    - URL and title extraction
    - Optional datetime parsing
    
    Args:
        raw_feed: Raw HTML/XML string containing blog post listings.
        default_source: Source identifier to assign to discovered BlogPost objects.
                        Defaults to "nvidia_tech_blog".
    
    Returns:
        List of BlogPost objects successfully parsed from the feed.
        Empty list if no valid posts are found or if parsing fails entirely.
    
    Example:
        >>> html = '''
        ... <div class="post">
        ...   <a class="post-link" href="https://developer.nvidia.com/blog/post-1">Post 1</a>
        ...   <time datetime="2025-01-02">Jan 2, 2025</time>
        ... </div>
        ... '''
        >>> posts = discover_posts_from_feed(html)
        >>> len(posts)
        1
        >>> posts[0].title
        'Post 1'
    
    Note:
        - Entries without valid URLs or titles are skipped
        - Whitespace is trimmed from titles and tags
        - The function will not raise on minor HTML quirks; malformed entries
          are silently skipped
    """
    if not raw_feed or not raw_feed.strip():
        return []
    
    try:
        soup = BeautifulSoup(raw_feed, "html.parser")
    except Exception:
        # If parsing fails entirely, return empty list
        return []
    
    # Find all post containers
    # Look for div.post first, then fall back to other common patterns
    post_containers = soup.find_all("div", class_="post")
    
    # If no div.post found, try other patterns
    if not post_containers:
        # Try article tags
        post_containers = soup.find_all("article")
    
    if not post_containers:
        # Try any div with a link inside
        post_containers = [
            elem for elem in soup.find_all("div")
            if elem.find("a")
        ]
    
    # Extract BlogPost objects from each container
    posts = []
    for container in post_containers:
        post = _extract_post_from_element(container, default_source)
        if post:
            posts.append(post)
    
    return posts

