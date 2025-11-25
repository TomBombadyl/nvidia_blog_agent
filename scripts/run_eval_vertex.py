#!/usr/bin/env python3
"""Evaluation script for Vertex AI RAG backend.

This script:
1. Loads configuration from environment variables
2. Creates real RAG retrieve client and Gemini QA model (Vertex RAG)
3. Defines evaluation test cases
4. Runs evaluation using the eval harness
5. Prints summary and detailed results

Usage:
    python scripts/run_eval_vertex.py
    python scripts/run_eval_vertex.py --verbose
    python scripts/run_eval_vertex.py --output results.json

Environment Variables:
    Must have USE_VERTEX_RAG=true and all Vertex RAG config set (see README.md)
"""

import asyncio
import argparse
import json
import sys
import logging
from datetime import datetime

# Note: This script assumes nvidia_blog_agent is installed (e.g., via `pip install -e .`)

from nvidia_blog_agent.config import load_config_from_env
from nvidia_blog_agent.rag_clients import create_rag_clients
from nvidia_blog_agent.agents.gemini_qa_model import GeminiQaModel
from nvidia_blog_agent.agents.qa_agent import QAAgent
from nvidia_blog_agent.eval.harness import (
    EvalCase,
    run_qa_evaluation,
    summarize_eval_results,
)


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_default_eval_cases() -> list[EvalCase]:
    """Create default evaluation test cases.

    These are example cases. Replace with your own based on actual NVIDIA blog content.
    """
    return [
        EvalCase(
            question="What did NVIDIA say about RAG on GPUs?",
            expected_substrings=["RAG", "GPU"],
            max_docs=8,
        ),
        EvalCase(
            question="How does CUDA acceleration work?",
            expected_substrings=["CUDA", "acceleration"],
            max_docs=10,
        ),
        EvalCase(
            question="What are the benefits of using TensorRT?",
            expected_substrings=["TensorRT"],
            max_docs=8,
        ),
        EvalCase(
            question="Explain NVIDIA's approach to generative AI.",
            expected_substrings=["generative", "AI"],
            max_docs=10,
        ),
    ]


async def main():
    """Main entrypoint for evaluation."""
    parser = argparse.ArgumentParser(
        description="Run evaluation against Vertex AI RAG backend"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file for results (JSON format). If not provided, prints to stdout.",
    )
    parser.add_argument(
        "--cases-file",
        type=str,
        default=None,
        help="JSON file containing custom eval cases. If not provided, uses default cases.",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Load configuration
        logger.info("Loading configuration from environment...")
        config = load_config_from_env()

        if not config.rag.use_vertex_rag:
            logger.warning(
                "⚠️  USE_VERTEX_RAG is not set to 'true'. This script is designed for Vertex RAG evaluation."
            )
            logger.warning(
                "   Continuing anyway, but results may not reflect Vertex RAG performance."
            )

        logger.info(f"Using Gemini model: {config.gemini.model_name}")
        logger.info(
            f"Using RAG backend: {'Vertex AI' if config.rag.use_vertex_rag else 'HTTP'}"
        )
        logger.info(f"RAG corpus ID: {config.rag.uuid}")
        logger.info(f"Vertex location: {config.rag.vertex_location}")

        # Create RAG clients (we only need retrieve client for evaluation)
        logger.info("Creating RAG clients...")
        ingest_client, retrieve_client = create_rag_clients(config)

        # Create QA model and agent
        logger.info("Initializing QA model and agent...")
        qa_model = GeminiQaModel(config.gemini)
        qa_agent = QAAgent(rag_client=retrieve_client, model=qa_model)

        # Load eval cases
        if args.cases_file:
            logger.info(f"Loading eval cases from {args.cases_file}...")
            with open(args.cases_file, "r") as f:
                cases_data = json.load(f)
            eval_cases = [
                EvalCase(
                    question=case["question"],
                    expected_substrings=case["expected_substrings"],
                    max_docs=case.get("max_docs", 8),
                )
                for case in cases_data
            ]
        else:
            logger.info(
                "Using default eval cases. Use --cases-file to provide custom cases."
            )
            eval_cases = create_default_eval_cases()

        logger.info(f"Running evaluation with {len(eval_cases)} test cases...")
        logger.info("=" * 80)

        # Run evaluation
        results = await run_qa_evaluation(qa_agent, eval_cases)

        # Summarize results
        summary = summarize_eval_results(results)

        # Print summary
        print("\n" + "=" * 80)
        print("EVALUATION SUMMARY")
        print("=" * 80)
        print(f"Total cases: {summary.total}")
        print(f"Passed: {summary.passed}")
        print(f"Failed: {summary.failed}")
        print(f"Pass rate: {summary.pass_rate:.2%}")
        print("=" * 80)

        # Print detailed results
        print("\n" + "=" * 80)
        print("DETAILED RESULTS")
        print("=" * 80)

        for i, result in enumerate(results, 1):
            status = "✅ PASS" if result.passed else "❌ FAIL"
            print(f"\n[{i}] {status} - {result.question}")
            # Find the corresponding case to get expected_substrings
            case = eval_cases[i - 1] if i <= len(eval_cases) else None
            if case:
                print(f"    Expected substrings: {case.expected_substrings}")
            print(f"    Matched: {result.matched_substrings}")
            print(f"    Retrieved docs: {len(result.retrieved_docs)}")
            if result.retrieved_docs:
                print(
                    f"    Top doc: {result.retrieved_docs[0].title} (score: {result.retrieved_docs[0].score:.4f})"
                )
            answer_preview = (
                result.answer[:200] + "..."
                if len(result.answer) > 200
                else result.answer
            )
            print(f"    Answer preview: {answer_preview}")

        print("\n" + "=" * 80)

        # Prepare output data
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "gemini_model": config.gemini.model_name,
                "rag_backend": "Vertex AI" if config.rag.use_vertex_rag else "HTTP",
                "corpus_id": config.rag.uuid,
                "vertex_location": config.rag.vertex_location,
            },
            "summary": {
                "total": summary.total,
                "passed": summary.passed,
                "failed": summary.failed,
                "pass_rate": summary.pass_rate,
            },
            "results": [
                {
                    "question": r.question,
                    "expected_substrings": eval_cases[i].expected_substrings
                    if i < len(eval_cases)
                    else [],
                    "matched_substrings": r.matched_substrings,
                    "passed": r.passed,
                    "retrieved_docs_count": len(r.retrieved_docs),
                    "answer": r.answer,
                    "retrieved_docs": [
                        {
                            "title": doc.title,
                            "url": str(doc.url),
                            "score": doc.score,
                        }
                        for doc in r.retrieved_docs[:3]  # Top 3 docs
                    ],
                }
                for i, r in enumerate(results)
            ],
        }

        # Save or print output
        if args.output:
            logger.info(f"Saving results to {args.output}...")
            with open(args.output, "w") as f:
                json.dump(output_data, f, indent=2)
            logger.info(f"✅ Results saved to {args.output}")
        else:
            print("\n" + "=" * 80)
            print("JSON OUTPUT (for ENGINEERING_STATUS_REPORT.md)")
            print("=" * 80)
            print(json.dumps(output_data, indent=2))

        logger.info("✅ Evaluation completed successfully!")
        return 0

    except KeyError as e:
        logger.error(f"❌ Missing required environment variable: {e}")
        logger.error("Please set the required environment variables (see README.md)")
        return 1
    except Exception as e:
        logger.error(f"❌ Evaluation failed: {e}", exc_info=args.verbose)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
