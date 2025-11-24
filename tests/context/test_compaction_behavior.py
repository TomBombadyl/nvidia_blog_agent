"""Tests for ingestion history compaction behavior.

Tests cover:
- append_ingestion_history_entry basic append functionality
- compact_ingestion_history with various scenarios
- Edge cases (empty state, non-list values, etc.)
"""

import pytest
from datetime import datetime, UTC
from nvidia_blog_agent.context.compaction import (
    INGESTION_HISTORY_KEY,
    append_ingestion_history_entry,
    compact_ingestion_history,
)


class TestAppendIngestionHistoryEntry:
    """Tests for append_ingestion_history_entry helper."""
    
    def test_basic_append(self):
        """Test basic append functionality."""
        state = {}
        metadata1 = {"discovered_count": 5, "new_count": 2}
        metadata2 = {"discovered_count": 3, "new_count": 1}
        
        timestamp1 = datetime(2024, 1, 15, 10, 0, 0)
        timestamp2 = datetime(2024, 1, 16, 10, 0, 0)
        
        append_ingestion_history_entry(state, metadata1, timestamp=timestamp1)
        append_ingestion_history_entry(state, metadata2, timestamp=timestamp2)
        
        # Verify history exists and is a list
        assert INGESTION_HISTORY_KEY in state
        history = state[INGESTION_HISTORY_KEY]
        assert isinstance(history, list)
        assert len(history) == 2
        
        # Verify first entry
        assert history[0]["timestamp"] == timestamp1.isoformat()
        assert history[0]["metadata"] == metadata1
        
        # Verify second entry
        assert history[1]["timestamp"] == timestamp2.isoformat()
        assert history[1]["metadata"] == metadata2
    
    def test_append_uses_utcnow_if_no_timestamp(self):
        """Test that append uses datetime.now(UTC) if timestamp not provided."""
        state = {}
        metadata = {"discovered_count": 5}
        
        before = datetime.now(UTC)
        append_ingestion_history_entry(state, metadata)
        after = datetime.now(UTC)
        
        history = state[INGESTION_HISTORY_KEY]
        assert len(history) == 1
        
        entry_timestamp = datetime.fromisoformat(history[0]["timestamp"])
        assert before <= entry_timestamp <= after
    
    def test_append_creates_list_if_missing(self):
        """Test that append creates a list if INGESTION_HISTORY_KEY is missing."""
        state = {}
        metadata = {"discovered_count": 5}
        
        append_ingestion_history_entry(state, metadata)
        
        assert INGESTION_HISTORY_KEY in state
        assert isinstance(state[INGESTION_HISTORY_KEY], list)
    
    def test_append_creates_list_if_not_list(self):
        """Test that append creates a new list if value is not a list."""
        state = {
            INGESTION_HISTORY_KEY: "not a list"
        }
        metadata = {"discovered_count": 5}
        
        append_ingestion_history_entry(state, metadata)
        
        history = state[INGESTION_HISTORY_KEY]
        assert isinstance(history, list)
        assert len(history) == 1
    
    def test_metadata_is_shallow_copied(self):
        """Test that metadata dict is shallow copied to avoid mutation."""
        state = {}
        original_metadata = {"discovered_count": 5, "new_count": 2}
        
        append_ingestion_history_entry(state, original_metadata)
        
        # Modify original
        original_metadata["discovered_count"] = 10
        
        # Stored metadata should be unchanged
        history = state[INGESTION_HISTORY_KEY]
        assert history[0]["metadata"]["discovered_count"] == 5


class TestCompactIngestionHistory:
    """Tests for compact_ingestion_history helper."""
    
    def test_below_limit_no_change(self):
        """Test that history below max_entries limit is unchanged."""
        state = {
            INGESTION_HISTORY_KEY: [
                {"timestamp": "2024-01-15T10:00:00", "metadata": {"count": 1}},
                {"timestamp": "2024-01-16T10:00:00", "metadata": {"count": 2}},
            ]
        }
        
        original_history = state[INGESTION_HISTORY_KEY].copy()
        
        compact_ingestion_history(state, max_entries=10)
        
        # Should be unchanged
        assert state[INGESTION_HISTORY_KEY] == original_history
        assert len(state[INGESTION_HISTORY_KEY]) == 2
    
    def test_at_limit_no_change(self):
        """Test that history at max_entries limit is unchanged."""
        state = {
            INGESTION_HISTORY_KEY: [
                {"timestamp": f"2024-01-{i:02d}T10:00:00", "metadata": {"count": i}}
                for i in range(1, 11)
            ]
        }
        
        original_history = state[INGESTION_HISTORY_KEY].copy()
        
        compact_ingestion_history(state, max_entries=10)
        
        # Should be unchanged
        assert state[INGESTION_HISTORY_KEY] == original_history
        assert len(state[INGESTION_HISTORY_KEY]) == 10
    
    def test_above_limit_trims_to_max(self):
        """Test that history above limit is trimmed to max_entries."""
        # Create 15 entries with identifiable metadata
        state = {
            INGESTION_HISTORY_KEY: [
                {"timestamp": f"2024-01-{i:02d}T10:00:00", "metadata": {"id": i, "count": i}}
                for i in range(1, 16)
            ]
        }
        
        compact_ingestion_history(state, max_entries=10)
        
        # Should keep only the last 10 entries
        history = state[INGESTION_HISTORY_KEY]
        assert len(history) == 10
        
        # Should keep entries 6-15 (the newest ones)
        assert history[0]["metadata"]["id"] == 6
        assert history[-1]["metadata"]["id"] == 15
    
    def test_keeps_newest_entries(self):
        """Test that compaction keeps the newest entries (last in list)."""
        state = {
            INGESTION_HISTORY_KEY: [
                {"timestamp": "2024-01-01T10:00:00", "metadata": {"id": "old1"}},
                {"timestamp": "2024-01-02T10:00:00", "metadata": {"id": "old2"}},
                {"timestamp": "2024-01-03T10:00:00", "metadata": {"id": "old3"}},
                {"timestamp": "2024-01-04T10:00:00", "metadata": {"id": "new1"}},
                {"timestamp": "2024-01-05T10:00:00", "metadata": {"id": "new2"}},
            ]
        }
        
        compact_ingestion_history(state, max_entries=2)
        
        history = state[INGESTION_HISTORY_KEY]
        assert len(history) == 2
        assert history[0]["metadata"]["id"] == "new1"
        assert history[1]["metadata"]["id"] == "new2"
    
    def test_empty_state_no_error(self):
        """Test that empty state doesn't cause an error."""
        state = {}
        
        # Should not raise
        compact_ingestion_history(state, max_entries=10)
        
        # State should remain empty
        assert INGESTION_HISTORY_KEY not in state or state.get(INGESTION_HISTORY_KEY) is None
    
    def test_missing_key_no_error(self):
        """Test that missing INGESTION_HISTORY_KEY doesn't cause an error."""
        state = {"other_key": "value"}
        
        # Should not raise
        compact_ingestion_history(state, max_entries=10)
        
        # State should be unchanged
        assert INGESTION_HISTORY_KEY not in state
    
    def test_non_list_value_no_error(self):
        """Test that non-list value doesn't cause an error."""
        state = {
            INGESTION_HISTORY_KEY: "not a list"
        }
        
        # Should not raise
        compact_ingestion_history(state, max_entries=10)
        
        # Value should remain unchanged (no-op)
        assert state[INGESTION_HISTORY_KEY] == "not a list"
    
    def test_custom_max_entries(self):
        """Test that custom max_entries parameter works."""
        state = {
            INGESTION_HISTORY_KEY: [
                {"timestamp": f"2024-01-{i:02d}T10:00:00", "metadata": {"id": i}}
                for i in range(1, 21)
            ]
        }
        
        compact_ingestion_history(state, max_entries=5)
        
        assert len(state[INGESTION_HISTORY_KEY]) == 5
        # Should keep entries 16-20
        assert state[INGESTION_HISTORY_KEY][0]["metadata"]["id"] == 16
        assert state[INGESTION_HISTORY_KEY][-1]["metadata"]["id"] == 20
    
    def test_zero_max_entries_clears_history(self):
        """Test that max_entries=0 clears the history."""
        state = {
            INGESTION_HISTORY_KEY: [
                {"timestamp": "2024-01-01T10:00:00", "metadata": {"count": 1}},
                {"timestamp": "2024-01-02T10:00:00", "metadata": {"count": 2}},
            ]
        }
        
        compact_ingestion_history(state, max_entries=0)
        
        assert len(state[INGESTION_HISTORY_KEY]) == 0

