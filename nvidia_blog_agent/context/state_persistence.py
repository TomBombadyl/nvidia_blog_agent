"""State persistence helpers for loading and saving application state.

This module provides functions to persist and restore application state,
supporting both local JSON file storage and GCS blob storage. The state
is stored in a format compatible with the session state helpers in
session_config.py and compaction.py.
"""

import json
import os
from pathlib import Path
from typing import MutableMapping, Any

try:
    from google.cloud import storage

    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    storage = None


def load_state_from_file(file_path: str) -> dict[str, Any]:
    """Load state from a local JSON file.

    Args:
        file_path: Path to the JSON file containing state.

    Returns:
        Dictionary containing the loaded state. Empty dict if file doesn't exist.

    Raises:
        IOError: If file exists but cannot be read or parsed.

    Example:
        >>> state = load_state_from_file("state.json")
        >>> "app:last_seen_blog_ids" in state
        True
    """
    path = Path(file_path)
    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise IOError(f"Failed to parse JSON from {file_path}: {e}") from e
    except Exception as e:
        raise IOError(f"Failed to read state from {file_path}: {e}") from e


def save_state_to_file(state: MutableMapping[str, Any], file_path: str) -> None:
    """Save state to a local JSON file.

    Creates the directory if it doesn't exist. Overwrites existing file.

    Args:
        state: State dictionary to save.
        file_path: Path to the JSON file to write.

    Raises:
        IOError: If file cannot be written.

    Example:
        >>> state = {"app:last_seen_blog_ids": ["id1", "id2"]}
        >>> save_state_to_file(state, "state.json")
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dict(state), f, indent=2, ensure_ascii=False)
    except Exception as e:
        raise IOError(f"Failed to write state to {file_path}: {e}") from e


def load_state_from_gcs(bucket_name: str, blob_name: str) -> dict[str, Any]:
    """Load state from a GCS blob.

    Args:
        bucket_name: Name of the GCS bucket (without gs:// prefix).
        blob_name: Name/path of the blob within the bucket.

    Returns:
        Dictionary containing the loaded state. Empty dict if blob doesn't exist.

    Raises:
        ImportError: If google-cloud-storage is not installed.
        IOError: If blob exists but cannot be read or parsed.

    Example:
        >>> state = load_state_from_gcs("nvidia-blog-agent-state", "state.json")
        >>> "app:last_seen_blog_ids" in state
        True
    """
    if not GCS_AVAILABLE:
        raise ImportError(
            "google-cloud-storage is required for GCS state persistence. "
            "Install with: pip install google-cloud-storage"
        )

    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        if not blob.exists():
            return {}

        content = blob.download_as_text(encoding="utf-8")
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise IOError(
            f"Failed to parse JSON from gs://{bucket_name}/{blob_name}: {e}"
        ) from e
    except Exception as e:
        raise IOError(
            f"Failed to read state from gs://{bucket_name}/{blob_name}: {e}"
        ) from e


def save_state_to_gcs(
    state: MutableMapping[str, Any],
    bucket_name: str,
    blob_name: str,
) -> None:
    """Save state to a GCS blob.

    Args:
        state: State dictionary to save.
        bucket_name: Name of the GCS bucket (without gs:// prefix).
        blob_name: Name/path of the blob within the bucket.

    Raises:
        ImportError: If google-cloud-storage is not installed.
        IOError: If blob cannot be written.

    Example:
        >>> state = {"app:last_seen_blog_ids": ["id1", "id2"]}
        >>> save_state_to_gcs(state, "nvidia-blog-agent-state", "state.json")
    """
    if not GCS_AVAILABLE:
        raise ImportError(
            "google-cloud-storage is required for GCS state persistence. "
            "Install with: pip install google-cloud-storage"
        )

    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        content = json.dumps(dict(state), indent=2, ensure_ascii=False)
        blob.upload_from_string(content, content_type="application/json")
    except Exception as e:
        raise IOError(
            f"Failed to write state to gs://{bucket_name}/{blob_name}: {e}"
        ) from e


def load_state(state_path: str | None = None) -> dict[str, Any]:
    """Load state from file or GCS based on the path format.

    If state_path starts with "gs://", loads from GCS.
    Otherwise, treats it as a local file path.

    If state_path is None, uses the STATE_PATH environment variable,
    or defaults to "state.json" in the current directory.

    Args:
        state_path: Path to state file or GCS URI (e.g., "gs://bucket/blob.json").
                   If None, uses STATE_PATH env var or "state.json".

    Returns:
        Dictionary containing the loaded state. Empty dict if source doesn't exist.

    Example:
        >>> # Load from local file
        >>> state = load_state("state.json")
        >>> # Load from GCS
        >>> state = load_state("gs://my-bucket/state.json")
    """
    if state_path is None:
        state_path = os.environ.get("STATE_PATH", "state.json")

    if state_path.startswith("gs://"):
        # Parse GCS URI: gs://bucket-name/blob-name
        path_parts = state_path[5:].split("/", 1)
        if len(path_parts) != 2:
            raise ValueError(
                f"Invalid GCS URI format: {state_path}. Expected gs://bucket/blob"
            )
        bucket_name, blob_name = path_parts
        return load_state_from_gcs(bucket_name, blob_name)
    else:
        return load_state_from_file(state_path)


def save_state(state: MutableMapping[str, Any], state_path: str | None = None) -> None:
    """Save state to file or GCS based on the path format.

    If state_path starts with "gs://", saves to GCS.
    Otherwise, treats it as a local file path.

    If state_path is None, uses the STATE_PATH environment variable,
    or defaults to "state.json" in the current directory.

    Args:
        state: State dictionary to save.
        state_path: Path to state file or GCS URI (e.g., "gs://bucket/blob.json").
                   If None, uses STATE_PATH env var or "state.json".

    Example:
        >>> state = {"app:last_seen_blog_ids": ["id1"]}
        >>> # Save to local file
        >>> save_state(state, "state.json")
        >>> # Save to GCS
        >>> save_state(state, "gs://my-bucket/state.json")
    """
    if state_path is None:
        state_path = os.environ.get("STATE_PATH", "state.json")

    if state_path.startswith("gs://"):
        # Parse GCS URI: gs://bucket-name/blob-name
        path_parts = state_path[5:].split("/", 1)
        if len(path_parts) != 2:
            raise ValueError(
                f"Invalid GCS URI format: {state_path}. Expected gs://bucket/blob"
            )
        bucket_name, blob_name = path_parts
        save_state_to_gcs(state, bucket_name, blob_name)
    else:
        save_state_to_file(state, state_path)
