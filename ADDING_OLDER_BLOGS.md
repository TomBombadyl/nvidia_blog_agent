# Adding Older Tech Blogs

## Overview

The ingestion system supports processing historical blog posts through multiple methods. The feed URL is configurable, and you can process multiple feeds or archive pages.

## Methods to Add Older Blogs

### Method 1: Custom Feed URL via API

The `/ingest` endpoint accepts an optional `feed_url` parameter:

```bash
curl -X POST https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/ingest \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"feed_url": "https://developer.nvidia.com/blog/feed/?paged=1"}'
```

**Note**: Many blog platforms support paginated feeds:
- WordPress: `?paged=1`, `?paged=2`, etc.
- Custom pagination: Check the blog's feed structure

### Method 2: Using the Local Script

The `scripts/run_ingest.py` script accepts a `--feed-url` parameter:

```bash
python scripts/run_ingest.py --feed-url "https://developer.nvidia.com/blog/feed/?paged=1"
```

### Method 3: Process Multiple Feeds (Script)

To process multiple pages/feeds, you can create a simple script:

```python
import asyncio
from scripts.run_ingest import main
import sys

async def ingest_multiple_feeds():
    """Process multiple feed pages."""
    base_url = "https://developer.nvidia.com/blog/feed/"
    
    for page in range(1, 10):  # Process pages 1-9
        feed_url = f"{base_url}?paged={page}" if page > 1 else base_url
        print(f"\nProcessing page {page}: {feed_url}")
        
        # Temporarily modify sys.argv to pass feed_url
        original_argv = sys.argv.copy()
        sys.argv = ["run_ingest.py", "--feed-url", feed_url]
        
        try:
            await main()
        except Exception as e:
            print(f"Error processing page {page}: {e}")
        finally:
            sys.argv = original_argv
        
        # Small delay between pages
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(ingest_multiple_feeds())
```

### Method 4: Modify Default Feed URL

To change the default feed URL permanently, edit:

**File**: `nvidia_blog_agent/tools/http_fetcher.py`

```python
async def fetch_feed_html(feed_url: str | None = None) -> str:
    if feed_url is None:
        # Change this default URL
        feed_url = "https://developer.nvidia.com/blog/feed/"  # Your custom URL here
```

### Method 5: Process Archive Pages

If the blog has archive pages (e.g., by year/month), you can:

1. **Create a list of archive URLs**:
   ```python
   archive_urls = [
       "https://developer.nvidia.com/blog/2024/",
       "https://developer.nvidia.com/blog/2023/",
       "https://developer.nvidia.com/blog/2022/",
   ]
   ```

2. **Process each archive** (the discovery tool can parse HTML pages, not just feeds):
   ```bash
   python scripts/run_ingest.py --feed-url "https://developer.nvidia.com/blog/2024/"
   ```

## Important Notes

### State Management

The system tracks processed blog posts by ID to avoid duplicates. When processing older blogs:

- **First run**: All posts will be treated as new (no existing IDs)
- **Subsequent runs**: Only truly new posts will be processed
- **State location**: Check `STATE_PATH` environment variable or use `--state-path` flag

### Feed Format Support

The system supports:
- ✅ **RSS 2.0 feeds** (`<rss>`)
- ✅ **Atom feeds** (`<feed>`)
- ✅ **HTML pages** (with post links)

### Rate Limiting

When processing many older posts:
- The system processes posts concurrently (efficient)
- Consider adding delays between feed pages if processing many
- Monitor Cloud Run logs for any rate limiting issues

## Example: Processing Historical NVIDIA Blogs

```bash
# Process current feed (default)
python scripts/run_ingest.py

# Process page 2 of feed
python scripts/run_ingest.py --feed-url "https://developer.nvidia.com/blog/feed/?paged=2"

# Process 2023 archive
python scripts/run_ingest.py --feed-url "https://developer.nvidia.com/blog/2023/"

# Process via API
curl -X POST https://nvidia-blog-agent-yuav3bbrka-uc.a.run.app/ingest \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"feed_url": "https://developer.nvidia.com/blog/feed/?paged=2"}'
```

## Troubleshooting

1. **Feed returns 403/404**: Try using RSS feed URL instead of HTML page
2. **No posts discovered**: Check if the feed format is supported (RSS/Atom/HTML)
3. **Duplicate posts**: The state management should prevent this, but verify `STATE_PATH` is set correctly

