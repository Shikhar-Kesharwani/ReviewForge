"""
Redis Caching & Rate Limiting Abstraction for ReviewForge.
Supports Upstash Redis (Cloud) and Redis container (Local).
Falls back to in-memory dictionary if Redis is unconfigured.
"""

import os
from typing import Optional, Any


class CacheManager:
    """Caching abstraction layer supporting Redis and local dictionary fallback."""
    def __init__(self):
        self.redis_client = None
        self._local_cache = {}
        self._init_redis()

    def _init_redis(self):
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return

        try:
            import redis
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
        except Exception as e:
            print(f"ℹ Redis notice: Running without external Redis ({e})")
            self.redis_client = None

    def get(self, key: str) -> Optional[str]:
        if self.redis_client:
            try:
                return self.redis_client.get(key)
            except Exception:
                pass
        return self._local_cache.get(key)

    def set(self, key: str, value: str, ex: int = 3600):
        if self.redis_client:
            try:
                self.redis_client.set(key, value, ex=ex)
                return
            except Exception:
                pass
        self._local_cache[key] = value

    def is_redis_active(self) -> bool:
        return self.redis_client is not None


_cache_instance = None


def get_cache() -> CacheManager:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheManager()
    return _cache_instance
