"""Example Kaggle Notebook code for interacting with the NVIDIA Blog Agent API.

This script demonstrates how to call the Cloud Run service from a Kaggle notebook
or any Python environment. Copy this code into a Kaggle notebook cell.

Usage in Kaggle:
    1. Create a new Kaggle notebook
    2. Add this code to a code cell
    3. Update SERVICE_URL with your Cloud Run service URL
    4. Run the cells
"""

import requests
import pandas as pd
from typing import Dict, Any


# Update this with your Cloud Run service URL
# Get it from: gcloud run services describe nvidia-blog-agent --region us-central1 --format='value(status.url)'
SERVICE_URL = (
    "https://YOUR-SERVICE-URL-HERE.run.app"  # Replace with your actual service URL
)


def ask(question: str, top_k: int = 8, timeout: int = 60) -> Dict[str, Any]:
    """Ask a question to the NVIDIA Blog Agent API.

    Args:
        question: The question to ask
        top_k: Number of documents to retrieve (default: 8)
        timeout: Request timeout in seconds (default: 60)

    Returns:
        Dictionary with 'answer' and 'sources' keys

    Raises:
        requests.HTTPError: If the API request fails
    """
    response = requests.post(
        f"{SERVICE_URL}/ask",
        json={"question": question, "top_k": top_k},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def display_answer(result: Dict[str, Any]) -> None:
    """Pretty-print the answer and sources.

    Args:
        result: Response dictionary from ask()
    """
    print("=" * 80)
    print("ANSWER")
    print("=" * 80)
    print(result["answer"])
    print("\n" + "=" * 80)
    print(f"SOURCES ({len(result['sources'])} documents)")
    print("=" * 80)

    # Create a DataFrame for better display
    sources_df = pd.DataFrame(result["sources"])
    if not sources_df.empty:
        # Reorder columns for better readability
        display_cols = ["title", "url", "score"]
        if "snippet" in sources_df.columns:
            display_cols.append("snippet")

        # Show only available columns
        available_cols = [c for c in display_cols if c in sources_df.columns]
        print(sources_df[available_cols].to_string(index=False))
    else:
        print("(No sources retrieved)")


# Example usage
if __name__ == "__main__":
    # Example 1: Simple question
    print("Example 1: Simple Question\n")
    result = ask("What did NVIDIA say about RAG on GPUs?")
    display_answer(result)

    # Example 2: Multiple questions with evaluation
    print("\n\n" + "=" * 80)
    print("Example 2: Evaluation on Multiple Questions")
    print("=" * 80)

    test_questions = [
        "What did NVIDIA say about RAG on GPUs?",
        "How does CUDA acceleration work?",
        "What are the benefits of using TensorRT?",
    ]

    results = []
    for question in test_questions:
        try:
            result = ask(question, top_k=8)
            results.append(
                {
                    "question": question,
                    "answer_length": len(result["answer"]),
                    "sources_count": len(result["sources"]),
                    "top_score": result["sources"][0]["score"]
                    if result["sources"]
                    else 0.0,
                    "status": "✅ Success",
                }
            )
        except Exception as e:
            results.append(
                {
                    "question": question,
                    "answer_length": 0,
                    "sources_count": 0,
                    "top_score": 0.0,
                    "status": f"❌ Error: {str(e)[:50]}",
                }
            )

    # Display results as a table
    eval_df = pd.DataFrame(results)
    print("\nEvaluation Results:")
    print(eval_df.to_string(index=False))

    # Calculate pass rate
    passed = sum(1 for r in results if r["status"] == "✅ Success")
    total = len(results)
    pass_rate = (passed / total) * 100 if total > 0 else 0

    print(f"\nPass Rate: {passed}/{total} ({pass_rate:.1f}%)")
