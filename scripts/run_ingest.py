#!/usr/bin/env python3
"""Entrypoint script for running the ingestion pipeline.

This script:
1. Loads configuration from environment variables
2. Loads persisted state (local JSON or GCS)
3. Fetches the NVIDIA Tech Blog feed HTML
4. Runs the ingestion pipeline (discovery → scrape → summarize → ingest)
5. Updates state with new post IDs and ingestion metadata
6. Saves updated state back to storage

Usage:
    python scripts/run_ingest.py [--state-path STATE_PATH] [--feed-url FEED_URL]

Environment Variables:
    See README.md for required configuration (GEMINI_MODEL_NAME, RAG config, etc.)
"""

import asyncio
import argparse
import sys
import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# If GOOGLE_APPLICATION_CREDENTIALS is set to a placeholder path, unset it to use ADC
if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").startswith(
    "/path/to/"
) or not os.path.exists(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")):
    if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
        del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

# Note: This script assumes nvidia_blog_agent is installed (e.g., via `pip install -e .`)
# No sys.path manipulation needed when package is properly installed

from nvidia_blog_agent.config import load_config_from_env  # noqa: E402
from nvidia_blog_agent.rag_clients import create_rag_clients  # noqa: E402
from nvidia_blog_agent.agents.workflow import run_ingestion_pipeline  # noqa: E402
from nvidia_blog_agent.agents.gemini_summarizer import GeminiSummarizer  # noqa: E402
from nvidia_blog_agent.tools.http_fetcher import HttpHtmlFetcher, fetch_feed_html  # noqa: E402
from nvidia_blog_agent.context.session_config import (  # noqa: E402
    get_existing_ids_from_state,
    update_existing_ids_in_state,
    store_last_ingestion_result_metadata,
)
from nvidia_blog_agent.context.compaction import (  # noqa: E402
    append_ingestion_history_entry,
    compact_ingestion_history,
)
from nvidia_blog_agent.context.state_persistence import load_state, save_state  # noqa: E402


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Main entrypoint for ingestion pipeline."""
    parser = argparse.ArgumentParser(
        description="Run the NVIDIA Blog ingestion pipeline"
    )
    parser.add_argument(
        "--state-path",
        type=str,
        default=None,
        help="Path to state file (local JSON or gs://bucket/blob). Defaults to STATE_PATH env var or 'state.json'",
    )
    parser.add_argument(
        "--feed-url",
        type=str,
        default=None,
        help="URL of the blog feed to fetch. Defaults to https://developer.nvidia.com/blog",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Load configuration
        logger.info("Loading configuration from environment...")
        config = load_config_from_env()
        logger.info(f"Using Gemini model: {config.gemini.model_name}")
        logger.info(
            f"Using RAG backend: {'Vertex AI' if config.rag.use_vertex_rag else 'HTTP'}"
        )

        # Create RAG clients
        logger.info("Creating RAG clients...")
        ingest_client, retrieve_client = create_rag_clients(config)

        # Load state
        logger.info(f"Loading state from: {args.state_path or 'default location'}...")
        state = load_state(args.state_path)
        existing_ids = get_existing_ids_from_state(state)
        logger.info(f"Found {len(existing_ids)} previously seen blog post IDs")

        # Fetch feed HTML
        logger.info("Fetching blog feed HTML...")
        feed_html = await fetch_feed_html(args.feed_url)
        logger.info(f"Fetched {len(feed_html)} bytes of feed HTML")

        # Create dependencies
        fetcher = HttpHtmlFetcher()
        summarizer = GeminiSummarizer(config.gemini)

        # Run ingestion pipeline
        logger.info("Running ingestion pipeline...")
        result = await run_ingestion_pipeline(
            feed_html=feed_html,
            existing_ids=existing_ids,
            fetcher=fetcher,
            summarizer=summarizer,
            rag_client=ingest_client,
        )

        # Log results
        logger.info(f"Discovery: {len(result.discovered_posts)} posts found in feed")
        logger.info(f"New posts: {len(result.new_posts)} posts to process")
        logger.info(f"Scraped: {len(result.raw_contents)} raw contents")
        logger.info(f"Summarized: {len(result.summaries)} summaries")

        if result.summaries:
            logger.info("Ingested summaries:")
            for summary in result.summaries[:5]:  # Show first 5
                logger.info(f"  - {summary.title}")
            if len(result.summaries) > 5:
                logger.info(f"  ... and {len(result.summaries) - 5} more")

        # Update state
        logger.info("Updating state...")
        update_existing_ids_in_state(state, result.new_posts)
        store_last_ingestion_result_metadata(state, result)

        # Append to history and compact
        from nvidia_blog_agent.context.session_config import (
            get_last_ingestion_result_metadata,
        )

        metadata = get_last_ingestion_result_metadata(state)
        append_ingestion_history_entry(state, metadata)
        compact_ingestion_history(state, max_entries=10)

        # Save state
        logger.info("Saving updated state...")
        save_state(state, args.state_path)

        logger.info("✅ Ingestion pipeline completed successfully!")
        return 0

    except KeyError as e:
        logger.error(f"❌ Missing required environment variable: {e}")
        logger.error("Please set the required environment variables (see README.md)")
        return 1
    except Exception as e:
        logger.error(f"❌ Ingestion pipeline failed: {e}", exc_info=args.verbose)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
