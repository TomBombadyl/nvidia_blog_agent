"""Caching module for request/response caching.

This module provides:
- Response caching for common queries
- TTL-based cache expiration
- Cache statistics
"""

import os
import hashlib
import json
import time
from typing import Optional, Any, Dict
from dataclasses import dataclass
from cachetools import TTLCache


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    size: int = 0
    max_size: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class ResponseCache:
    """TTL-based response cache."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """Initialize response cache.
        
        Args:
            max_size: Maximum number of cached items
            ttl_seconds: Time-to-live in seconds (default: 1 hour)
        """
        self._cache = TTLCache(maxsize=max_size, ttl=ttl_seconds)
        self._hits = 0
        self._misses = 0
    
    def _make_key(self, endpoint: str, **kwargs) -> str:
        """Generate cache key from endpoint and parameters."""
        # Sort kwargs for consistent key generation
        params = json.dumps(kwargs, sort_keys=True, default=str)
        key_data = f"{endpoint}:{params}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def get(self, endpoint: str, **kwargs) -> Optional[Any]:
        """Get cached response.
        
        Args:
            endpoint: API endpoint path
            **kwargs: Request parameters
            
        Returns:
            Cached response or None if not found
        """
        key = self._make_key(endpoint, **kwargs)
        result = self._cache.get(key)
        
        if result is not None:
            self._hits += 1
        else:
            self._misses += 1
        
        return result
    
    def set(self, endpoint: str, value: Any, **kwargs):
        """Cache a response.
        
        Args:
            endpoint: API endpoint path
            value: Response value to cache
            **kwargs: Request parameters
        """
        key = self._make_key(endpoint, **kwargs)
        self._cache[key] = value
    
    def clear(self):
        """Clear all cached items."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return CacheStats(
            hits=self._hits,
            misses=self._misses,
            size=len(self._cache),
            max_size=self._cache.maxsize
        )


# Global cache instance
_response_cache: Optional[ResponseCache] = None


def get_response_cache() -> ResponseCache:
    """Get the global response cache instance."""
    global _response_cache
    if _response_cache is None:
        max_size = int(os.environ.get("CACHE_MAX_SIZE", "1000"))
        ttl_seconds = int(os.environ.get("CACHE_TTL_SECONDS", "3600"))
        _response_cache = ResponseCache(max_size=max_size, ttl_seconds=ttl_seconds)
    return _response_cache

