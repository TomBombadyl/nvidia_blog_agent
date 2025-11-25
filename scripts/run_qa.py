#!/usr/bin/env python3
"""Entrypoint script for running QA queries.

This script:
1. Loads configuration from environment variables
2. Creates RAG retrieve client and Gemini QA model
3. Accepts a question (CLI arg or stdin)
4. Runs QAAgent to answer the question
5. Prints the answer and retrieved document titles/URLs

Usage:
    python scripts/run_qa.py "What did NVIDIA say about RAG?"
    echo "What is GPU acceleration?" | python scripts/run_qa.py

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
if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").startswith("/path/to/") or (
    os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    and not os.path.exists(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""))
):
    if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
        del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

# Note: This script assumes nvidia_blog_agent is installed (e.g., via `pip install -e .`)
# No sys.path manipulation needed when package is properly installed

from nvidia_blog_agent.config import load_config_from_env  # noqa: E402
from nvidia_blog_agent.rag_clients import create_rag_clients  # noqa: E402
from nvidia_blog_agent.agents.gemini_qa_model import GeminiQaModel  # noqa: E402
from nvidia_blog_agent.agents.qa_agent import QAAgent  # noqa: E402


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Main entrypoint for QA queries."""
    parser = argparse.ArgumentParser(description="Query the NVIDIA Blog RAG system")
    parser.add_argument(
        "question",
        nargs="?",
        type=str,
        default=None,
        help="Question to ask. If not provided, reads from stdin.",
    )
    parser.add_argument(
        "--top-k",
        "-k",
        type=int,
        default=5,
        help="Number of documents to retrieve (default: 5)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get question from arg or stdin
    question = args.question
    if not question:
        logger.info("Reading question from stdin...")
        question = sys.stdin.read().strip()

    if not question:
        logger.error("❌ No question provided. Provide via argument or stdin.")
        return 1

    try:
        # Load configuration
        logger.info("Loading configuration from environment...")
        config = load_config_from_env()
        logger.info(f"Using Gemini model: {config.gemini.model_name}")
        logger.info(
            f"Using RAG backend: {'Vertex AI' if config.rag.use_vertex_rag else 'HTTP'}"
        )

        # Create RAG clients (we only need retrieve client for QA)
        logger.info("Creating RAG clients...")
        ingest_client, retrieve_client = create_rag_clients(config)

        # Create QA model and agent
        logger.info("Initializing QA model and agent...")
        qa_model = GeminiQaModel(config.gemini)
        qa_agent = QAAgent(rag_client=retrieve_client, model=qa_model)

        # Run QA query
        logger.info(f"Querying: {question}")
        logger.info(f"Retrieving top {args.top_k} documents...")
        answer, retrieved_docs = await qa_agent.answer(question, k=args.top_k)

        # Print results
        print("\n" + "=" * 80)
        print("QUESTION:")
        print("=" * 80)
        print(question)
        print("\n" + "=" * 80)
        print("ANSWER:")
        print("=" * 80)
        print(answer)
        print("\n" + "=" * 80)
        print(f"RETRIEVED DOCUMENTS ({len(retrieved_docs)}):")
        print("=" * 80)

        if retrieved_docs:
            for i, doc in enumerate(retrieved_docs, 1):
                print(f"\n[{i}] {doc.title}")
                print(f"    URL: {doc.url}")
                print(f"    Score: {doc.score:.4f}")
                if doc.snippet:
                    snippet_preview = (
                        doc.snippet[:200] + "..."
                        if len(doc.snippet) > 200
                        else doc.snippet
                    )
                    print(f"    Snippet: {snippet_preview}")
        else:
            print("(No documents retrieved)")

        print("=" * 80 + "\n")

        logger.info("✅ QA query completed successfully!")
        return 0

    except KeyError as e:
        logger.error(f"❌ Missing required environment variable: {e}")
        logger.error("Please set the required environment variables (see README.md)")
        return 1
    except Exception as e:
        logger.error(f"❌ QA query failed: {e}", exc_info=args.verbose)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
