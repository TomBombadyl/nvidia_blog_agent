"""Discovery tools for finding and tracking NVIDIA tech blog posts.

This module provides pure, deterministic functions for:
- Parsing blog feeds/HTML into BlogPost objects
- Diffing newly discovered posts against previously seen IDs

These tools are designed to be:
- Pure functions (no side effects)
- Deterministic and testable
- Ready for integration with ADK function tools
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional, Iterable
from bs4 import BeautifulSoup, Tag
from nvidia_blog_agent.contracts.blog_models import BlogPost, generate_post_id


def diff_new_posts(
    existing_ids: Iterable[str], discovered_posts: Iterable[BlogPost]
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
    return [post for post in discovered_posts if post.id not in existing_set]


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
    element: Tag, default_source: str = "nvidia_tech_blog"
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

    # Extract categories/tags from the element
    tags = []

    # Method 1: Look for explicit tag elements with class="tag"
    tag_elements = element.find_all(class_="tag")
    for tag_elem in tag_elements:
        tag_text = tag_elem.get_text(strip=True)
        if tag_text:
            tags.append(tag_text)

    # Method 2: Look for category information in parent sections or nearby elements
    # Check for category labels in parent containers (common patterns on blog landing pages)
    parent = element.parent
    if parent:
        # Look for category text in parent's class or data attributes
        category_attrs = parent.get("class", []) or []
        for attr in category_attrs:
            if "category" in attr.lower() or "tag" in attr.lower():
                tags.append(attr)

        # Look for category in nearby headings or labels
        category_heading = parent.find(
            ["h2", "h3", "h4", "span"],
            class_=lambda x: x
            and ("category" in x.lower() or "tag" in x.lower() if x else False),
        )
        if category_heading:
            cat_text = category_heading.get_text(strip=True)
            if cat_text and cat_text not in tags:
                tags.append(cat_text)

    # Method 3: Look for category in data attributes
    category_data = element.get("data-category") or element.get("data-tag")
    if category_data:
        tags.append(category_data)

    # Method 4: Look for category in nearby text that matches common NVIDIA blog category patterns
    # Common categories: "Simulation / Modeling / Design", "Agentic AI / Generative AI", etc.
    nearby_text = element.get_text()
    if nearby_text:
        # Look for category patterns in the text (e.g., "Category: X" or section headers)
        import re

        category_patterns = [
            r"Category:\s*([^\n]+)",
            r"Topic:\s*([^\n]+)",
        ]
        for pattern in category_patterns:
            matches = re.findall(pattern, nearby_text, re.IGNORECASE)
            for match in matches:
                cat = match.strip()
                if cat and cat not in tags:
                    tags.append(cat)

    try:
        return BlogPost(
            id=post_id,
            url=url_str,
            title=title,
            published_at=published_at,
            tags=tags,
            source=default_source,
        )
    except Exception:
        # If BlogPost validation fails, skip this entry
        return None


def _parse_atom_feed(raw_feed: str, default_source: str) -> List[BlogPost]:
    """Parse Atom/RSS XML feed into BlogPost objects.

    Supports both Atom and RSS 2.0 feed formats.

    Args:
        raw_feed: Raw XML string containing Atom or RSS feed.
        default_source: Source identifier for BlogPost objects.

    Returns:
        List of BlogPost objects parsed from the feed.
    """
    posts = []

    try:
        # Parse XML (Atom and RSS feeds use XML)
        root = ET.fromstring(raw_feed)

        # Determine feed type by root element
        is_rss = root.tag == "rss" or root.tag.endswith("}rss")
        is_atom = root.tag == "feed" or root.tag.endswith("}feed")

        # Handle namespaces (for future use if needed)
        # namespaces = {
        #     "atom": "http://www.w3.org/2005/Atom",
        #     "content": "http://purl.org/rss/1.0/modules/content/",
        # }

        # Find all entry/item elements
        entries = []
        if is_atom:
            # Atom format uses <entry>
            entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
            if not entries:
                entries = root.findall(".//entry")
        elif is_rss:
            # RSS 2.0 format uses <item>
            # RSS structure: rss -> channel -> item
            channel = root.find("channel")
            if channel is None:
                channel = root.find("{http://www.w3.org/2005/Atom}channel")
            if channel is not None:
                entries = channel.findall("item")
                if not entries:
                    entries = channel.findall("{http://www.w3.org/2005/Atom}item")
        else:
            # Try both formats
            entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
            if not entries:
                entries = root.findall(".//entry")
            if not entries:
                channel = root.find("channel")
                if channel is not None:
                    entries = channel.findall("item")

        for entry in entries:
            try:
                # Extract title (works for both Atom and RSS)
                title_elem = entry.find("{http://www.w3.org/2005/Atom}title")
                if title_elem is None:
                    title_elem = entry.find("title")
                if title_elem is None:
                    continue

                # Get title text (ElementTree automatically handles CDATA)
                # Get all text content including from nested elements
                title_text = (title_elem.text or "") + "".join(
                    (elem.text or "") + (elem.tail or "") for elem in title_elem
                )
                # Remove HTML tags from title
                title_text = re.sub(r"<[^>]+>", "", title_text)
                # Decode HTML entities (basic ones)
                title_text = (
                    title_text.replace("&amp;", "&")
                    .replace("&lt;", "<")
                    .replace("&gt;", ">")
                    .replace("&quot;", '"')
                    .replace("&#39;", "'")
                )
                title_text = title_text.strip()
                if not title_text:
                    continue

                # Extract URL from link element (Atom) or guid/link (RSS)
                url = None
                if is_atom or not is_rss:
                    # Atom format: <link href="...">
                    link_elems = entry.findall("{http://www.w3.org/2005/Atom}link")
                    if not link_elems:
                        link_elems = entry.findall("link")

                    for link in link_elems:
                        rel = link.get("rel", "alternate")
                        if (
                            rel == "alternate"
                            or link.get("type") == "text/html"
                            or not link.get("rel")
                        ):
                            url = link.get("href")
                            if url:
                                break
                else:
                    # RSS 2.0 format: <link>...</link> or <guid>...</guid>
                    link_elem = entry.find("link")
                    if link_elem is not None and link_elem.text:
                        url = link_elem.text.strip()
                    if not url:
                        guid_elem = entry.find("guid")
                        if guid_elem is not None and guid_elem.text:
                            url = guid_elem.text.strip()

                if not url:
                    continue

                # Extract published date
                published_at = None
                if is_atom or not is_rss:
                    # Atom format: <published> or <updated>
                    published_elem = entry.find(
                        "{http://www.w3.org/2005/Atom}published"
                    )
                    if published_elem is None:
                        published_elem = entry.find("published")
                    if published_elem is None:
                        published_elem = entry.find(
                            "{http://www.w3.org/2005/Atom}updated"
                        )
                        if published_elem is None:
                            published_elem = entry.find("updated")
                else:
                    # RSS 2.0 format: <pubDate>
                    published_elem = entry.find("pubDate")

                if published_elem is not None and published_elem.text:
                    published_at = _parse_datetime(published_elem.text)

                # Extract categories/tags
                tags = []
                if is_atom or not is_rss:
                    # Atom format: <category term="...">
                    category_elems = entry.findall(
                        "{http://www.w3.org/2005/Atom}category"
                    )
                    if not category_elems:
                        category_elems = entry.findall("category")

                    for cat in category_elems:
                        term = cat.get("term", "").strip()
                        if term:
                            tags.append(term)
                else:
                    # RSS 2.0 format: <category>...</category>
                    category_elems = entry.findall("category")
                    for cat in category_elems:
                        cat_text = (cat.text or "").strip()
                        if cat_text:
                            tags.append(cat_text)

                # Extract content from feed (if available)
                # Atom feeds use <content>, RSS 2.0 uses <description> or <content:encoded>
                content = None
                if is_atom or not is_rss:
                    # Atom format: <content type="html">...</content>
                    content_elem = entry.find("{http://www.w3.org/2005/Atom}content")
                    if content_elem is None:
                        content_elem = entry.find("content")

                    if content_elem is not None:
                        # Check content type - prefer HTML content
                        content_type = content_elem.get("type", "text")
                        if content_type in ("html", "xhtml", "text/html"):
                            # Get content text - ElementTree handles CDATA automatically
                            content_text = content_elem.text or ""
                            # Also get text from nested elements
                            if not content_text:
                                content_text = "".join(
                                    (elem.text or "") + (elem.tail or "")
                                    for elem in content_elem
                                )
                            # Get full XML representation if it's XHTML
                            if content_type == "xhtml" and not content_text:
                                # For XHTML, get the full XML structure of child elements
                                xhtml_parts = []
                                for child in content_elem:
                                    xhtml_parts.append(
                                        ET.tostring(
                                            child, encoding="unicode", method="html"
                                        )
                                    )
                                if xhtml_parts:
                                    content_text = "".join(xhtml_parts)
                            content = content_text.strip() if content_text else None
                else:
                    # RSS 2.0 format: <content:encoded> (preferred) or <description>
                    content_elem = entry.find(
                        "{http://purl.org/rss/1.0/modules/content/}encoded"
                    )
                    if content_elem is None:
                        # Fall back to description (may be summary only)
                        content_elem = entry.find("description")

                    if content_elem is not None:
                        # Get content text - ElementTree handles CDATA automatically
                        content_text = content_elem.text or ""
                        # Also get text from nested elements
                        if not content_text:
                            content_text = "".join(
                                (elem.text or "") + (elem.tail or "")
                                for elem in content_elem
                            )
                        content = content_text.strip() if content_text else None

                # Generate stable ID from URL
                post_id = generate_post_id(url)

                # Create BlogPost
                post = BlogPost(
                    id=post_id,
                    url=url,
                    title=title_text,
                    published_at=published_at,
                    tags=tags,
                    source=default_source,
                    content=content,
                )
                posts.append(post)

            except Exception:
                # Skip malformed entries
                continue

    except ET.ParseError:
        # Not valid XML, return empty list
        return []
    except Exception:
        # Other parsing errors, return empty list
        return []

    return posts


def discover_posts_from_feed(
    raw_feed: str, *, default_source: str = "nvidia_tech_blog"
) -> List[BlogPost]:
    """Parse HTML/XML feed content into a list of BlogPost objects.

    This function automatically detects the feed format and parses accordingly:
    - Atom/RSS XML feeds (preferred - faster, more reliable)
    - HTML blog index pages (fallback)

    For Atom/RSS feeds, it extracts:
    - Title, URL, published date, categories/tags

    For HTML pages, it extracts:
    - Title, URL, published date from HTML structure

    Args:
        raw_feed: Raw HTML/XML string containing blog post listings.
        default_source: Source identifier to assign to discovered BlogPost objects.
                        Defaults to "nvidia_tech_blog".

    Returns:
        List of BlogPost objects successfully parsed from the feed.
        Empty list if no valid posts are found or if parsing fails entirely.

    Example:
        >>> # Atom feed
        >>> atom_xml = '''<?xml version="1.0"?><feed><entry><title>Post 1</title>...</entry></feed>'''
        >>> posts = discover_posts_from_feed(atom_xml)
        >>> # HTML feed
        >>> html = '''<div class="post"><a href="...">Post 1</a></div>'''
        >>> posts = discover_posts_from_feed(html)
    """
    if not raw_feed or not raw_feed.strip():
        return []

    # Try parsing as Atom/RSS feed first (preferred method)
    # Check if it looks like XML
    raw_feed_stripped = raw_feed.strip()
    if (
        raw_feed_stripped.startswith("<?xml")
        or raw_feed_stripped.startswith("<feed")
        or raw_feed_stripped.startswith("<rss")
        or "<feed" in raw_feed_stripped[:100]
        or "<rss" in raw_feed_stripped[:100]
    ):
        atom_posts = _parse_atom_feed(raw_feed, default_source)
        if atom_posts:
            return atom_posts
        # If Atom/RSS parsing fails, fall through to HTML parsing

    # Fall back to HTML parsing
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
        post_containers = [elem for elem in soup.find_all("div") if elem.find("a")]

    # Extract BlogPost objects from each container
    posts = []
    for container in post_containers:
        post = _extract_post_from_element(container, default_source)
        if post:
            posts.append(post)

    return posts
