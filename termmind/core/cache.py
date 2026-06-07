"""LRU cache layer for performance."""

from typing import Any, Optional
from collections import OrderedDict
import time
import hashlib


class Cache:
    """Simple LRU cache with TTL support.
    
    Usage:
        cache = Cache(max_size=1000, default_ttl=3600)
        cache.set("key", "value", ttl=300)
        value = cache.get("key")
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600) -> None:
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._hits = 0
        self._misses = 0
    
    def _key(self, *args: Any, **kwargs: Any) -> str:
        """Generate a cache key."""
        key_data = f"{args}:{kwargs}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key not in self._cache:
            self._misses += 1
            return None
        
        value, expiry = self._cache[key]
        if time.time() > expiry:
            del self._cache[key]
            self._misses += 1
            return None
        
        self._hits += 1
        self._cache.move_to_end(key)
        return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        if len(self._cache) >= self.max_size and key not in self._cache:
            self._cache.popitem(last=False)
        
        expiry = time.time() + (ttl or self.default_ttl)
        self._cache[key] = (value, expiry)
        self._cache.move_to_end(key)
    
    def clear(self) -> None:
        """Clear all cache."""
        self._cache.clear()
    
    def invalidate(self, pattern: str) -> int:
        """Invalidate keys matching pattern. Returns count removed."""
        keys_to_remove = [k for k in self._cache.keys() if pattern in k]
        for k in keys_to_remove:
            del self._cache[k]
        return len(keys_to_remove)
    
    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0,
        }
