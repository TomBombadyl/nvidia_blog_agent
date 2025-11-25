"""Tests for session state prefix helpers and ingestion state management.

Tests cover:
- get_existing_ids_from_state with various state configurations
- update_existing_ids_in_state with new and overlapping posts
- store_last_ingestion_result_metadata and get_last_ingestion_result_metadata
- Prefix constant validation
"""

import pytest
from nvidia_blog_agent.contracts.blog_models import (
    BlogPost,
    RawBlogContent,
    BlogSummary,
)
from nvidia_blog_agent.agents.workflow import IngestionResult
from nvidia_blog_agent.context.session_config import (
    APP_PREFIX,
    USER_PREFIX,
    TEMP_PREFIX,
    APP_LAST_SEEN_IDS_KEY,
    APP_LAST_INGESTION_RESULTS_KEY,
    get_existing_ids_from_state,
    update_existing_ids_in_state,
    store_last_ingestion_result_metadata,
    get_last_ingestion_result_metadata,
)


class TestPrefixConstants:
    """Tests for prefix constant values."""

    def test_prefix_constants(self):
        """Test that prefix constants have expected values."""
        assert APP_PREFIX == "app:"
        assert USER_PREFIX == "user:"
        assert TEMP_PREFIX == "temp:"

    def test_app_keys_start_with_prefix(self):
        """Test that app-level keys start with APP_PREFIX."""
        assert APP_LAST_SEEN_IDS_KEY.startswith(APP_PREFIX)
        assert APP_LAST_INGESTION_RESULTS_KEY.startswith(APP_PREFIX)


class TestGetExistingIdsFromState:
    """Tests for get_existing_ids_from_state helper."""

    def test_empty_state_returns_empty_set(self):
        """Test that empty state returns empty set."""
        state = {}
        ids = get_existing_ids_from_state(state)
        assert ids == set()
        assert len(ids) == 0

    def test_state_with_list_of_ids(self):
        """Test that state with list of IDs returns set of strings."""
        state = {APP_LAST_SEEN_IDS_KEY: ["id1", "id2", "id3"]}
        ids = get_existing_ids_from_state(state)
        assert isinstance(ids, set)
        assert "id1" in ids
        assert "id2" in ids
        assert "id3" in ids
        assert len(ids) == 3

    def test_state_with_set_of_ids(self):
        """Test that state with set of IDs returns set of strings."""
        state = {APP_LAST_SEEN_IDS_KEY: {"id1", "id2", "id3"}}
        ids = get_existing_ids_from_state(state)
        assert isinstance(ids, set)
        assert "id1" in ids
        assert "id2" in ids
        assert "id3" in ids

    def test_state_with_tuple_of_ids(self):
        """Test that state with tuple of IDs returns set of strings."""
        state = {APP_LAST_SEEN_IDS_KEY: ("id1", "id2", "id3")}
        ids = get_existing_ids_from_state(state)
        assert isinstance(ids, set)
        assert "id1" in ids
        assert "id2" in ids
        assert "id3" in ids

    def test_state_with_none_value(self):
        """Test that state with None value returns empty set."""
        state = {APP_LAST_SEEN_IDS_KEY: None}
        ids = get_existing_ids_from_state(state)
        assert ids == set()

    def test_state_with_missing_key(self):
        """Test that missing key returns empty set."""
        state = {}
        ids = get_existing_ids_from_state(state)
        assert ids == set()

    def test_ids_normalized_to_strings(self):
        """Test that numeric IDs are normalized to strings."""
        state = {APP_LAST_SEEN_IDS_KEY: [1, 2, 3]}
        ids = get_existing_ids_from_state(state)
        assert "1" in ids
        assert "2" in ids
        assert "3" in ids
        assert all(isinstance(id_str, str) for id_str in ids)


class TestUpdateExistingIdsInState:
    """Tests for update_existing_ids_in_state helper."""

    def test_empty_state_adds_new_posts(self):
        """Test that empty state correctly adds new posts."""
        state = {}
        posts = [
            BlogPost(id="id1", url="https://example.com/1", title="Post 1"),
            BlogPost(id="id2", url="https://example.com/2", title="Post 2"),
        ]

        update_existing_ids_in_state(state, posts)

        assert APP_LAST_SEEN_IDS_KEY in state
        stored_ids = state[APP_LAST_SEEN_IDS_KEY]
        assert isinstance(stored_ids, list)
        assert stored_ids == ["id1", "id2"]  # Should be sorted
        assert len(stored_ids) == 2

    def test_existing_state_adds_new_posts(self):
        """Test that existing state correctly adds new posts."""
        state = {APP_LAST_SEEN_IDS_KEY: ["id1", "id2"]}
        posts = [
            BlogPost(id="id3", url="https://example.com/3", title="Post 3"),
        ]

        update_existing_ids_in_state(state, posts)

        stored_ids = state[APP_LAST_SEEN_IDS_KEY]
        assert "id1" in stored_ids
        assert "id2" in stored_ids
        assert "id3" in stored_ids
        assert len(stored_ids) == 3
        assert stored_ids == sorted(stored_ids)  # Should remain sorted

    def test_overlapping_posts_deduplicated(self):
        """Test that overlapping posts are deduplicated."""
        state = {APP_LAST_SEEN_IDS_KEY: ["id1", "id2"]}
        posts = [
            BlogPost(
                id="id2", url="https://example.com/2", title="Post 2"
            ),  # Duplicate
            BlogPost(id="id3", url="https://example.com/3", title="Post 3"),  # New
        ]

        update_existing_ids_in_state(state, posts)

        stored_ids = state[APP_LAST_SEEN_IDS_KEY]
        assert stored_ids.count("id2") == 1  # Should not be duplicated
        assert "id1" in stored_ids
        assert "id2" in stored_ids
        assert "id3" in stored_ids
        assert len(stored_ids) == 3

    def test_list_stays_sorted(self):
        """Test that the stored list remains sorted after updates."""
        state = {}
        posts = [
            BlogPost(id="id3", url="https://example.com/3", title="Post 3"),
            BlogPost(id="id1", url="https://example.com/1", title="Post 1"),
            BlogPost(id="id2", url="https://example.com/2", title="Post 2"),
        ]

        update_existing_ids_in_state(state, posts)

        stored_ids = state[APP_LAST_SEEN_IDS_KEY]
        assert stored_ids == ["id1", "id2", "id3"]  # Should be sorted


class TestStoreAndGetLastIngestionResultMetadata:
    """Tests for storing and retrieving ingestion result metadata."""

    def test_store_and_get_metadata(self):
        """Test storing and retrieving ingestion result metadata."""
        # Create a simple IngestionResult
        posts = [
            BlogPost(id="id1", url="https://example.com/1", title="Post 1"),
            BlogPost(id="id2", url="https://example.com/2", title="Post 2"),
        ]

        raw_contents = [
            RawBlogContent(
                blog_id="id1",
                url="https://example.com/1",
                title="Post 1",
                html="<html>Test</html>",
                text="Test content 1",
            ),
            RawBlogContent(
                blog_id="id2",
                url="https://example.com/2",
                title="Post 2",
                html="<html>Test</html>",
                text="Test content 2",
            ),
        ]

        summaries = [
            BlogSummary(
                blog_id="id1",
                title="Post 1",
                url="https://example.com/1",
                executive_summary="Executive summary 1",
                technical_summary="Technical summary 1 with enough content to meet validation requirements.",
            ),
            BlogSummary(
                blog_id="id2",
                title="Post 2",
                url="https://example.com/2",
                executive_summary="Executive summary 2",
                technical_summary="Technical summary 2 with enough content to meet validation requirements.",
            ),
        ]

        result = IngestionResult(
            discovered_posts=posts,
            new_posts=posts,
            raw_contents=raw_contents,
            summaries=summaries,
        )

        state = {}
        store_last_ingestion_result_metadata(state, result)

        # Verify stored
        assert APP_LAST_INGESTION_RESULTS_KEY in state

        # Retrieve and verify
        metadata = get_last_ingestion_result_metadata(state)
        assert metadata["discovered_count"] == 2
        assert metadata["new_count"] == 2
        assert metadata["raw_contents_count"] == 2
        assert metadata["summaries_count"] == 2
        assert metadata["last_titles"] == ["Post 1", "Post 2"]

    def test_last_titles_limited_to_five(self):
        """Test that last_titles is limited to 5 entries."""
        # Create result with 7 summaries
        summaries = [
            BlogSummary(
                blog_id=f"id{i}",
                title=f"Post {i}",
                url=f"https://example.com/{i}",
                executive_summary=f"Executive summary {i}",
                technical_summary=f"Technical summary {i} with enough content to meet validation requirements.",
            )
            for i in range(1, 8)
        ]

        result = IngestionResult(
            discovered_posts=[],
            new_posts=[],
            raw_contents=[],
            summaries=summaries,
        )

        state = {}
        store_last_ingestion_result_metadata(state, result)

        metadata = get_last_ingestion_result_metadata(state)
        assert len(metadata["last_titles"]) == 5
        assert metadata["last_titles"] == [
            "Post 1",
            "Post 2",
            "Post 3",
            "Post 4",
            "Post 5",
        ]

    def test_get_metadata_empty_state(self):
        """Test that get_metadata returns empty dict for empty state."""
        state = {}
        metadata = get_last_ingestion_result_metadata(state)
        assert metadata == {}

    def test_get_metadata_non_dict_value(self):
        """Test that get_metadata returns empty dict for non-dict value."""
        state = {APP_LAST_INGESTION_RESULTS_KEY: "not a dict"}
        metadata = get_last_ingestion_result_metadata(state)
        assert metadata == {}

    def test_store_metadata_raises_type_error_for_non_ingestion_result(self):
        """Test that store_metadata raises TypeError for non-IngestionResult."""
        state = {}
        with pytest.raises(TypeError) as exc_info:
            store_last_ingestion_result_metadata(state, "not an IngestionResult")
        assert "must be an IngestionResult" in str(exc_info.value)

    def test_metadata_is_shallow_copy(self):
        """Test that retrieved metadata is a shallow copy."""
        state = {
            APP_LAST_INGESTION_RESULTS_KEY: {
                "discovered_count": 5,
                "last_titles": ["Title 1"],
            }
        }

        metadata1 = get_last_ingestion_result_metadata(state)
        metadata2 = get_last_ingestion_result_metadata(state)

        # Modifying one shouldn't affect the other (shallow copy)
        metadata1["discovered_count"] = 10
        assert metadata2["discovered_count"] == 5
