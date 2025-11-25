#!/usr/bin/env python3
"""Test script to verify RSS feed parsing works with the actual NVIDIA feed.

This script:
1. Fetches the RSS feed from NVIDIA Tech Blog
2. Parses it to extract posts with content
3. Verifies that content is extracted correctly
4. Shows a summary of what was found
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import nvidia_blog_agent
sys.path.insert(0, str(Path(__file__).parent.parent))

from nvidia_blog_agent.tools.http_fetcher import fetch_feed_html
from nvidia_blog_agent.tools.discovery import discover_posts_from_feed


async def main():
    """Test RSS feed parsing."""
    print("Testing RSS feed parsing...")
    print()
    
    # Fetch the feed
    print("Fetching RSS feed from https://developer.nvidia.com/blog/feed/...")
    try:
        feed_xml = await fetch_feed_html()
        print(f"[OK] Fetched {len(feed_xml)} bytes")
        print()
    except Exception as e:
        print(f"[ERROR] Failed to fetch feed: {e}")
        return 1
    
    # Parse the feed
    print("Parsing feed...")
    try:
        posts = discover_posts_from_feed(feed_xml)
        print(f"[OK] Found {len(posts)} posts")
        print()
    except Exception as e:
        print(f"[ERROR] Failed to parse feed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    if not posts:
        print("[WARNING] No posts found in feed")
        return 1
    
    # Analyze results
    posts_with_content = [p for p in posts if p.content]
    posts_without_content = [p for p in posts if not p.content]
    
    print("Summary:")
    print(f"   Total posts: {len(posts)}")
    print(f"   Posts with content: {len(posts_with_content)}")
    print(f"   Posts without content: {len(posts_without_content)}")
    print()
    
    # Show sample posts
    print("Sample posts (first 3):")
    for i, post in enumerate(posts[:3], 1):
        print(f"\n   {i}. {post.title}")
        print(f"      URL: {post.url}")
        print(f"      Published: {post.published_at or 'N/A'}")
        print(f"      Tags: {', '.join(post.tags) if post.tags else 'None'}")
        has_content = "[YES]" if post.content else "[NO]"
        print(f"      Content from feed: {has_content}")
        if post.content:
            content_preview = post.content[:100].replace('\n', ' ')
            print(f"      Content preview: {content_preview}...")
    
    print()
    
    # Verify content quality
    if posts_with_content:
        avg_content_length = sum(len(p.content) for p in posts_with_content) / len(posts_with_content)
        print(f"Average content length: {avg_content_length:.0f} characters")
        
        # Check if content looks like HTML
        html_posts = [p for p in posts_with_content if '<' in p.content and '>' in p.content]
        print(f"   Posts with HTML content: {len(html_posts)}/{len(posts_with_content)}")
    
    print()
    print("[OK] RSS feed parsing test completed successfully!")
    
    if len(posts_with_content) > 0:
        print(f"[SUCCESS] Successfully extracted content from {len(posts_with_content)} posts!")
        print("   This means we can avoid fetching individual posts and 403 errors.")
    else:
        print("[WARNING] No posts have content in the feed. Will need to fetch individual posts.")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

