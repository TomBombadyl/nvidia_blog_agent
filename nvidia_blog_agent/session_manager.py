"""Session management for multi-turn conversations.

This module provides:
- Session-based conversation history
- Query history tracking
- Session cleanup
"""

import os
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, UTC, timedelta
from collections import defaultdict


@dataclass
class QueryHistory:
    """History entry for a single query."""
    question: str
    answer: str
    sources: List[Dict[str, Any]]
    timestamp: str
    latency_ms: float


@dataclass
class ConversationSession:
    """A conversation session with history."""
    session_id: str
    created_at: str
    last_activity: str
    queries: List[QueryHistory]
    
    def add_query(self, question: str, answer: str, sources: List[Dict], latency_ms: float):
        """Add a query to the session history."""
        self.queries.append(QueryHistory(
            question=question,
            answer=answer,
            sources=sources,
            timestamp=datetime.now(UTC).isoformat(),
            latency_ms=latency_ms
        ))
        self.last_activity = datetime.now(UTC).isoformat()
        # Keep only last 50 queries per session
        if len(self.queries) > 50:
            self.queries = self.queries[-50:]


class SessionManager:
    """Manages conversation sessions and query history."""
    
    def __init__(self, session_ttl_hours: int = 24):
        """Initialize session manager.
        
        Args:
            session_ttl_hours: Time-to-live for sessions in hours (default: 24)
        """
        self._sessions: Dict[str, ConversationSession] = {}
        self._session_ttl = timedelta(hours=session_ttl_hours)
        self._all_queries: List[QueryHistory] = []  # Global query history
    
    def create_session(self, session_id: Optional[str] = None) -> ConversationSession:
        """Create a new conversation session.
        
        Args:
            session_id: Optional custom session ID. If None, generates one.
        
        Returns:
            New ConversationSession instance
        """
        if session_id is None:
            session_id = f"session_{int(time.time() * 1000)}"
        
        session = ConversationSession(
            session_id=session_id,
            created_at=datetime.now(UTC).isoformat(),
            last_activity=datetime.now(UTC).isoformat(),
            queries=[]
        )
        self._sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Get an existing session.
        
        Args:
            session_id: Session ID
        
        Returns:
            ConversationSession or None if not found
        """
        session = self._sessions.get(session_id)
        if session:
            # Check if session has expired
            last_activity = datetime.fromisoformat(session.last_activity.replace('Z', '+00:00'))
            if datetime.now(UTC) - last_activity > self._session_ttl:
                del self._sessions[session_id]
                return None
        return session
    
    def add_query_to_session(
        self,
        session_id: str,
        question: str,
        answer: str,
        sources: List[Dict],
        latency_ms: float
    ):
        """Add a query to a session.
        
        Args:
            session_id: Session ID
            question: User question
            answer: Generated answer
            sources: Source documents
            latency_ms: Request latency in milliseconds
        """
        session = self.get_session(session_id)
        if not session:
            session = self.create_session(session_id)
        
        session.add_query(question, answer, sources, latency_ms)
        
        # Also add to global history
        query = QueryHistory(
            question=question,
            answer=answer,
            sources=sources,
            timestamp=datetime.now(UTC).isoformat(),
            latency_ms=latency_ms
        )
        self._all_queries.append(query)
        # Keep only last 10000 queries globally
        if len(self._all_queries) > 10000:
            self._all_queries = self._all_queries[-10000:]
    
    def get_session_history(self, session_id: str) -> Optional[List[QueryHistory]]:
        """Get query history for a session.
        
        Args:
            session_id: Session ID
        
        Returns:
            List of QueryHistory entries or None if session not found
        """
        session = self.get_session(session_id)
        return session.queries if session else None
    
    def get_all_queries(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[QueryHistory]:
        """Get all queries (across all sessions).
        
        Args:
            limit: Maximum number of queries to return
            offset: Offset for pagination
        
        Returns:
            List of QueryHistory entries
        """
        return self._all_queries[offset:offset + limit]
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions."""
        now = datetime.now(UTC)
        expired = []
        
        for session_id, session in self._sessions.items():
            last_activity = datetime.fromisoformat(session.last_activity.replace('Z', '+00:00'))
            if now - last_activity > self._session_ttl:
                expired.append(session_id)
        
        for session_id in expired:
            del self._sessions[session_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get session manager statistics.
        
        Returns:
            Dictionary with session counts and query statistics
        """
        self.cleanup_expired_sessions()
        
        total_queries = len(self._all_queries)
        active_sessions = len(self._sessions)
        
        return {
            "active_sessions": active_sessions,
            "total_queries": total_queries,
            "queries_per_session": (
                total_queries / active_sessions
                if active_sessions > 0
                else 0.0
            )
        }


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        ttl_hours = int(os.environ.get("SESSION_TTL_HOURS", "24"))
        _session_manager = SessionManager(session_ttl_hours=ttl_hours)
    return _session_manager

