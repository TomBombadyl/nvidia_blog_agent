"""Compaction helpers for ingestion history in session state.

This module provides:
- append_ingestion_history_entry: Add entries to ingestion history
- compact_ingestion_history: Trim history to keep only recent entries

The compaction uses a simple sliding window approach: keep only the most
recent N entries, dropping older ones. This prevents unbounded growth of
history in long-running sessions.
"""

from typing import MutableMapping, Any, Dict
from datetime import datetime, UTC
from nvidia_blog_agent.context.session_config import APP_PREFIX


# Key for storing ingestion history in state
INGESTION_HISTORY_KEY = f"{APP_PREFIX}ingestion_history"


def append_ingestion_history_entry(
    state: MutableMapping[str, Any],
    metadata: Dict[str, Any],
    *,
    timestamp: datetime | None = None,
) -> None:
    """Append a single ingestion metadata entry to the app-level ingestion history.

    Each entry is stored as a dict with:
    - timestamp: ISO8601 string
    - metadata: The metadata dict (shallow copied)

    The history is stored as a list under INGESTION_HISTORY_KEY. Entries are
    appended in chronological order, with the most recent entry at the end.

    Args:
        state: MutableMapping representing session state (e.g., ADK Session.state).
        metadata: Dictionary containing ingestion metadata (e.g., from
                 get_last_ingestion_result_metadata()).
        timestamp: Optional datetime for the entry. If None, uses datetime.utcnow().

    Example:
        >>> state = {}
        >>> metadata = {"discovered_count": 5, "new_count": 2}
        >>> append_ingestion_history_entry(state, metadata)
        >>> len(state[INGESTION_HISTORY_KEY])
        1
    """
    if timestamp is None:
        timestamp = datetime.now(UTC)

    entry = {
        "timestamp": timestamp.isoformat(),
        "metadata": dict(metadata),  # Shallow copy to avoid mutation
    }

    history = state.get(INGESTION_HISTORY_KEY)
    if not isinstance(history, list):
        history = []
    history.append(entry)
    state[INGESTION_HISTORY_KEY] = history


def compact_ingestion_history(
    state: MutableMapping[str, Any],
    *,
    max_entries: int = 10,
) -> None:
    """Compact the ingestion history by keeping at most max_entries entries.

    This function implements a simple sliding window compaction:
    - If history has <= max_entries entries, no change
    - If history has more, drops the oldest entries, keeping only the most
      recent max_entries

    Assumes entries are appended in chronological order (oldest first, newest last).
    Operates in-place on the state's INGESTION_HISTORY_KEY.

    Args:
        state: MutableMapping representing session state (e.g., ADK Session.state).
        max_entries: Maximum number of entries to keep. Defaults to 10.

    Example:
        >>> state = {INGESTION_HISTORY_KEY: [entry1, entry2, ..., entry15]}
        >>> compact_ingestion_history(state, max_entries=10)
        >>> len(state[INGESTION_HISTORY_KEY])
        10
    """
    history = state.get(INGESTION_HISTORY_KEY)
    if not isinstance(history, list):
        return

    if len(history) <= max_entries:
        return

    # If max_entries is 0, clear the history
    if max_entries == 0:
        state[INGESTION_HISTORY_KEY] = []
        return

    # Keep only the newest max_entries (assumes entries appended in time order)
    state[INGESTION_HISTORY_KEY] = history[-max_entries:]
