#!/usr/bin/env python3
"""Import RAG files from GCS bucket into Vertex AI RAG corpus.

This script imports all .txt files from the GCS bucket into the Vertex AI RAG corpus.
It uses the Vertex AI RAG API to import files.

Usage:
    python scripts/import_rag_files.py
"""

import asyncio
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from nvidia_blog_agent.config import load_config_from_env  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def wait_for_operation(
    client, operation_name, headers, location, project_id, max_wait_minutes=30
):
    """Wait for a long-running operation to complete."""
    from datetime import datetime, timedelta

    operation_endpoint = (
        f"https://{location}-aiplatform.googleapis.com/v1/{operation_name}"
    )

    start_time = datetime.now()
    timeout = start_time + timedelta(minutes=max_wait_minutes)

    while datetime.now() < timeout:
        response = await client.get(operation_endpoint, headers=headers)
        if response.status_code == 200:
            result = response.json()
            if result.get("done", False):
                if "error" in result:
                    logger.error(f"   ❌ Operation failed: {result['error']}")
                    return False
                logger.info("   ✅ Operation completed successfully")
                return True

        await asyncio.sleep(10)  # Check every 10 seconds

    logger.warning(f"   ⏰ Operation timed out after {max_wait_minutes} minutes")
    logger.info(f"   Check status manually: {operation_endpoint}")
    return False


async def import_rag_files_from_gcs():
    """Import all .txt files from GCS bucket into Vertex AI RAG corpus."""
    import httpx
    from google.auth import default
    from google.auth.transport.requests import Request as AuthRequest
    from google.cloud import storage

    # Load configuration
    config = load_config_from_env()

    if not config.rag.use_vertex_rag:
        logger.error("❌ Vertex AI RAG is not enabled. Set USE_VERTEX_RAG=true")
        return False

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
    location = config.rag.vertex_location
    corpus_id = config.rag.uuid
    bucket_name = config.rag.docs_bucket

    # Extract bucket name from gs:// URL if provided
    if bucket_name.startswith("gs://"):
        bucket_name = bucket_name[5:]
    bucket_name = bucket_name.rstrip("/")

    logger.info(f"📦 Project: {project_id}")
    logger.info(f"📍 Location: {location}")
    logger.info(f"🆔 Corpus ID: {corpus_id}")
    logger.info(f"🪣 Bucket: {bucket_name}")

    # List all .txt files in the bucket
    logger.info("🔍 Listing files in GCS bucket...")
    storage_client = storage.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)
    blobs = list(bucket.list_blobs())

    txt_files = [blob for blob in blobs if blob.name.endswith(".txt")]
    logger.info(f"✅ Found {len(txt_files)} .txt files in bucket")

    if not txt_files:
        logger.warning("⚠️  No .txt files found in bucket. Nothing to import.")
        return False

    # Build GCS URIs for all .txt files
    gcs_uris = [f"gs://{bucket_name}/{blob.name}" for blob in txt_files]
    logger.info(f"📄 Found {len(gcs_uris)} .txt files in bucket")

    # API limit: max 25 URIs per request, and only one operation at a time
    # So we need to batch and wait for each to complete
    BATCH_SIZE = 25
    batches = [
        gcs_uris[i : i + BATCH_SIZE] for i in range(0, len(gcs_uris), BATCH_SIZE)
    ]
    logger.info(
        f"📦 Will import in {len(batches)} batches (max {BATCH_SIZE} files per batch)"
    )

    # Construct import endpoint
    endpoint = (
        f"https://{location}-aiplatform.googleapis.com/v1beta1/"
        f"projects/{project_id}/locations/{location}/"
        f"ragCorpora/{corpus_id}/ragFiles:import"
    )

    # Get credentials
    credentials, _ = default()
    if not credentials.valid:
        credentials.refresh(AuthRequest())

    # Import each batch sequentially (wait for each to complete)
    async with httpx.AsyncClient(timeout=300.0) as client:
        token = credentials.token
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        operations = []
        for batch_idx, batch_uris in enumerate(batches, 1):
            logger.info("")
            logger.info(
                f"🚀 Importing batch {batch_idx}/{len(batches)} ({len(batch_uris)} files)..."
            )

            # Build request payload for this batch
            payload = {
                "import_rag_files_config": {
                    "gcs_source": {"uris": batch_uris},
                    "rag_file_chunking_config": {
                        "chunk_size": 1024,  # tokens
                        "chunk_overlap": 256,  # tokens
                    },
                }
            }

            # Retry if there's an operation in progress
            max_retries = 10
            retry_delay = 30  # seconds
            for attempt in range(max_retries):
                response = await client.post(endpoint, json=payload, headers=headers)

                if response.status_code == 200:
                    result = response.json()
                    if "name" in result:
                        operation_name = result["name"]
                        operations.append(operation_name)
                        logger.info(
                            f"   ✅ Batch {batch_idx} operation started: {operation_name}"
                        )
                        logger.info(
                            f"   ⏳ Waiting for batch {batch_idx} to complete..."
                        )

                        # Wait for operation to complete
                        await wait_for_operation(
                            client, operation_name, headers, location, project_id
                        )
                        logger.info(f"   ✅ Batch {batch_idx} completed!")
                    else:
                        logger.info(f"   ✅ Batch {batch_idx} completed immediately!")
                    break
                elif response.status_code == 400:
                    try:
                        error_body = response.json()
                        error_msg = error_body.get("error", {}).get("message", "")
                        if "other operations running" in error_msg:
                            if attempt < max_retries - 1:
                                logger.info(
                                    f"   ⏳ Another operation is running. Waiting {retry_delay}s (attempt {attempt + 1}/{max_retries})..."
                                )
                                await asyncio.sleep(retry_delay)
                                continue
                            else:
                                logger.error(
                                    f"   ❌ Operation still running after {max_retries} attempts"
                                )
                                logger.error(
                                    "   Please wait and run the script again later"
                                )
                                return False
                    except Exception:
                        pass

                # If we get here, it's a different error
                try:
                    error_body = response.json()
                except Exception:
                    error_body = response.text
                logger.error(
                    f"❌ API Error ({response.status_code}) for batch {batch_idx}: {error_body}"
                )
                response.raise_for_status()

    logger.info("")
    logger.info("✅ All batches imported successfully!")
    logger.info(f"   Total batches: {len(batches)}")
    logger.info(f"   Total files: {len(gcs_uris)}")
    logger.info("💡 Files are now being indexed. This may take a few minutes.")
    logger.info(
        f"   Check status: https://console.cloud.google.com/ai/rag?project={project_id}"
    )

    return True


async def main():
    """Main entrypoint."""
    try:
        success = await import_rag_files_from_gcs()
        if success:
            logger.info("✅ Import process completed successfully!")
            logger.info("")
            logger.info("⏳ Note: Importing and indexing may take several minutes.")
            logger.info("   Check the Vertex AI RAG console to monitor progress:")
            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get(
                "GCP_PROJECT"
            )
            logger.info(
                f"   https://console.cloud.google.com/ai/rag?project={project_id}"
            )
        else:
            logger.error("❌ Import process failed")
            sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Import failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
