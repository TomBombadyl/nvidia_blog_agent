"""Session state configuration and helpers for the NVIDIA Blog Agent.

This module provides:
- State key constants with prefix conventions (app:, user:, temp:)
- Helpers for managing ingestion-related state
- Functions for reading/writing blog IDs and ingestion metadata

All helpers operate on a generic MutableMapping[str, Any] state, making them
compatible with ADK Session.state while remaining testable with plain dicts.
"""

from typing import MutableMapping, Iterable, Set, Any, Dict
from nvidia_blog_agent.contracts.blog_models import BlogPost


# Prefix conventions for state keys
APP_PREFIX = "app:"
USER_PREFIX = "user:"
TEMP_PREFIX = "temp:"

# App-level keys for ingestion
APP_LAST_SEEN_IDS_KEY = f"{APP_PREFIX}last_seen_blog_ids"
APP_LAST_INGESTION_RESULTS_KEY = f"{APP_PREFIX}last_ingestion_results"


def get_existing_ids_from_state(state: MutableMapping[str, Any]) -> Set[str]:
    """Retrieve the set of previously-seen blog IDs from the state.
    
    Looks under APP_LAST_SEEN_IDS_KEY. If missing or None, returns an empty set.
    Values are normalized to a set of strings, accepting list, set, tuple, etc.
    
    Args:
        state: MutableMapping representing session state (e.g., ADK Session.state).
    
    Returns:
        Set of string IDs. Empty set if key is missing or value is None.
    
    Example:
        >>> state = {"app:last_seen_blog_ids": ["id1", "id2", "id3"]}
        >>> ids = get_existing_ids_from_state(state)
        >>> "id1" in ids
        True
    """
    value = state.get(APP_LAST_SEEN_IDS_KEY)
    if value is None:
        return set()
    # Accept list, set, tuple, etc. and normalize to set of strings
    return {str(v) for v in value}


def update_existing_ids_in_state(
    state: MutableMapping[str, Any],
    new_posts: Iterable[BlogPost],
) -> None:
    """Update the set of previously-seen blog IDs in the state with new_posts.
    
    This function:
    1. Reads existing IDs via get_existing_ids_from_state()
    2. Adds blog.id for each new post
    3. Writes back a sorted list of IDs to APP_LAST_SEEN_IDS_KEY
    
    The list is stored sorted for portability and JSON-friendliness.
    The helper always returns a set when reading, but stores as a list.
    
    Args:
        state: MutableMapping representing session state (e.g., ADK Session.state).
        new_posts: Iterable of BlogPost objects whose IDs should be added.
    
    Example:
        >>> state = {}
        >>> posts = [
        ...     BlogPost(id="id1", url="https://example.com/1", title="Post 1"),
        ...     BlogPost(id="id2", url="https://example.com/2", title="Post 2")
        ... ]
        >>> update_existing_ids_in_state(state, posts)
        >>> state[APP_LAST_SEEN_IDS_KEY]
        ['id1', 'id2']
    """
    existing = get_existing_ids_from_state(state)
    for post in new_posts:
        existing.add(post.id)
    # Store as sorted list for portability / JSON-friendliness
    state[APP_LAST_SEEN_IDS_KEY] = sorted(existing)


def store_last_ingestion_result_metadata(
    state: MutableMapping[str, Any],
    result: Any,  # IngestionResult - using Any to avoid circular import
) -> None:
    """Store lightweight metadata about the last ingestion run.
    
    Stores a JSON-serializable metadata structure under APP_LAST_INGESTION_RESULTS_KEY.
    The metadata includes counts and up to 5 most recent titles, avoiding storage
    of the full IngestionResult which could be large.
    
    Args:
        state: MutableMapping representing session state (e.g., ADK Session.state).
        result: IngestionResult object from run_ingestion_pipeline().
    
    Raises:
        TypeError: If result is not an IngestionResult instance.
    
    Example:
        >>> from nvidia_blog_agent.agents.workflow import IngestionResult
        >>> state = {}
        >>> result = IngestionResult(
        ...     discovered_posts=[...],
        ...     new_posts=[...],
        ...     raw_contents=[...],
        ...     summaries=[...]
        ... )
        >>> store_last_ingestion_result_metadata(state, result)
        >>> metadata = state[APP_LAST_INGESTION_RESULTS_KEY]
        >>> "discovered_count" in metadata
        True
    """
    # Local import to avoid circular dependency
    from nvidia_blog_agent.agents.workflow import IngestionResult
    
    if not isinstance(result, IngestionResult):
        raise TypeError("result must be an IngestionResult")
    
    # Store up to 5 most recent titles
    N = 5
    last_titles = [s.title for s in result.summaries[:N]]
    
    meta: Dict[str, Any] = {
        "discovered_count": len(result.discovered_posts),
        "new_count": len(result.new_posts),
        "raw_contents_count": len(result.raw_contents),
        "summaries_count": len(result.summaries),
        "last_titles": last_titles,
    }
    state[APP_LAST_INGESTION_RESULTS_KEY] = meta


def get_last_ingestion_result_metadata(
    state: MutableMapping[str, Any],
) -> Dict[str, Any]:
    """Get the stored metadata for the last ingestion run.
    
    Returns a shallow copy of the metadata dict to avoid accidental in-place mutation.
    Returns an empty dict if nothing was stored or if the value is not a dict.
    
    Args:
        state: MutableMapping representing session state (e.g., ADK Session.state).
    
    Returns:
        Dictionary containing ingestion metadata with keys:
        - discovered_count: int
        - new_count: int
        - raw_contents_count: int
        - summaries_count: int
        - last_titles: List[str] (up to 5 titles)
        Empty dict if no metadata is stored.
    
    Example:
        >>> state = {APP_LAST_INGESTION_RESULTS_KEY: {"discovered_count": 5, ...}}
        >>> metadata = get_last_ingestion_result_metadata(state)
        >>> metadata["discovered_count"]
        5
    """
    value = state.get(APP_LAST_INGESTION_RESULTS_KEY)
    if not isinstance(value, dict):
        return {}
    # Return shallow copy to avoid accidental mutation
    return dict(value)

