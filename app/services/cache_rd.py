"""
Cache em memória com TTL para requisições RD Station.
Evita chamadas redundantes à API e respeita rate limits.
"""
import time
from typing import Optional


class RDCache:
    def __init__(self, ttl: int = 600):
        self.ttl = ttl
        self._cache: dict = {}
        self._timestamps: dict = {}

    def get(self, key: str) -> Optional[dict]:
        if key not in self._cache:
            return None
        if time.time() - self._timestamps.get(key, 0) > self.ttl:
            del self._cache[key]
            self._timestamps.pop(key, None)
            return None
        return self._cache[key]

    def set(self, key: str, value: dict) -> None:
        self._cache[key] = value
        self._timestamps[key] = time.time()

    def delete(self, key: str) -> None:
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        keys = [k for k in self._cache if k.startswith(prefix)]
        for k in keys:
            self.delete(k)

    def size(self) -> int:
        return len(self._cache)


# Instância global — TTL 10 minutos
rd_cache = RDCache(ttl=600)
