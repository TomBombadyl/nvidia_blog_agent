#!/usr/bin/env python3
"""Local smoke test script for the FastAPI service.

This script tests the FastAPI service endpoints locally before deploying to Cloud Run.
It assumes the service is running on localhost:8080 (via uvicorn).

Usage:
    # Terminal 1: Start the service
    uvicorn service.app:app --reload --port 8080

    # Terminal 2: Run this test script
    python scripts/test_service_local.py
"""

import sys
import json
import httpx


SERVICE_URL = "http://localhost:8080"


def test_health() -> bool:
    """Test the /health endpoint."""
    print("Testing /health endpoint...")
    try:
        response = httpx.get(f"{SERVICE_URL}/health", timeout=10.0)
        response.raise_for_status()
        data = response.json()
        print(f"✅ Health check passed: {json.dumps(data, indent=2)}")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


def test_root() -> bool:
    """Test the / endpoint."""
    print("\nTesting / endpoint...")
    try:
        response = httpx.get(f"{SERVICE_URL}/", timeout=10.0)
        response.raise_for_status()
        data = response.json()
        print(f"✅ Root endpoint passed: {json.dumps(data, indent=2)}")
        return True
    except Exception as e:
        print(f"❌ Root endpoint failed: {e}")
        return False


def test_ask(
    question: str = "What did NVIDIA say about RAG on GPUs?", top_k: int = 8
) -> bool:
    """Test the /ask endpoint."""
    print(f"\nTesting /ask endpoint with question: '{question[:50]}...'")
    try:
        response = httpx.post(
            f"{SERVICE_URL}/ask",
            json={"question": question, "top_k": top_k},
            timeout=60.0,  # QA can take a while
        )
        response.raise_for_status()
        data = response.json()

        print("✅ Ask endpoint passed!")
        print(f"Answer: {data.get('answer', '')[:200]}...")
        print(f"Sources: {len(data.get('sources', []))} documents retrieved")

        if data.get("sources"):
            print("\nTop sources:")
            for i, source in enumerate(data["sources"][:3], 1):
                print(
                    f"  {i}. {source.get('title', 'N/A')} (score: {source.get('score', 0):.4f})"
                )

        return True
    except httpx.HTTPStatusError as e:
        print(
            f"❌ Ask endpoint failed with HTTP {e.response.status_code}: {e.response.text}"
        )
        return False
    except Exception as e:
        print(f"❌ Ask endpoint failed: {e}")
        return False


def test_mcp() -> bool:
    """Test the /mcp endpoint (MCP protocol endpoint)."""
    print("\nTesting /mcp endpoint (MCP protocol)...")
    try:
        # Test GET request (SSE endpoint)
        response = httpx.get(f"{SERVICE_URL}/mcp", timeout=10.0)
        # MCP endpoint might return different status codes, but shouldn't be 502
        if response.status_code == 502:
            print(f"❌ MCP endpoint returned 502 Bad Gateway (mount issue)")
            return False
        print(f"✅ MCP endpoint responded with status {response.status_code}")
        print(f"   (This is expected - MCP uses specific protocol)")
        return True
    except httpx.ConnectError:
        print("❌ MCP endpoint connection failed (service not running?)")
        return False
    except Exception as e:
        print(f"❌ MCP endpoint test failed: {e}")
        return False


def test_ingest(api_key: str | None = None) -> bool:
    """Test the /ingest endpoint."""
    print("\nTesting /ingest endpoint...")
    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key

        response = httpx.post(
            f"{SERVICE_URL}/ingest",
            json={},
            headers=headers,
            timeout=300.0,  # Ingestion can take a while
        )
        response.raise_for_status()
        data = response.json()

        print("✅ Ingest endpoint passed!")
        print(f"Discovered: {data.get('discovered_count', 0)} posts")
        print(f"New: {data.get('new_count', 0)} posts")
        print(f"Ingested: {data.get('ingested_count', 0)} summaries")
        print(f"Message: {data.get('message', 'N/A')}")

        return True
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            print("❌ Ingest endpoint requires API key (401 Unauthorized)")
            print("   Set INGEST_API_KEY env var and pass it to this script")
        else:
            print(
                f"❌ Ingest endpoint failed with HTTP {e.response.status_code}: {e.response.text}"
            )
        return False
    except Exception as e:
        print(f"❌ Ingest endpoint failed: {e}")
        return False


def main():
    """Run all smoke tests."""
    import os

    print("=" * 80)
    print("NVIDIA Blog Agent - Local Service Smoke Test")
    print("=" * 80)
    print(f"Service URL: {SERVICE_URL}")
    print("\nMake sure the service is running:")
    print("  uvicorn service.app:app --reload --port 8080")
    print("=" * 80)

    results = []

    # Test health
    results.append(("Health", test_health()))

    # Test root
    results.append(("Root", test_root()))

    # Test ask
    results.append(("Ask", test_ask()))

    # Test MCP endpoint
    results.append(("MCP", test_mcp()))

    # Test ingest (optional, may require API key)
    ingest_api_key = os.environ.get("INGEST_API_KEY")
    if ingest_api_key:
        print("\nUsing INGEST_API_KEY from environment")
        results.append(("Ingest", test_ingest(api_key=ingest_api_key)))
    else:
        print("\nSkipping /ingest test (set INGEST_API_KEY env var to test)")
        print("  Note: /ingest may require API key if configured in the service")
        results.append(("Ingest", None))

    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    for name, result in results:
        if result is None:
            print(f"{name}: ⏭️  Skipped")
        elif result:
            print(f"{name}: ✅ Passed")
        else:
            print(f"{name}: ❌ Failed")

    passed = sum(1 for _, r in results if r is True)
    total = sum(1 for _, r in results if r is not None)

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Service is ready for Cloud Run deployment.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Fix issues before deploying to Cloud Run.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
