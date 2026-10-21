"""Tiny in-process TTL cache (single-server deployments)."""

import threading
import time


class TTLCache:
    def __init__(self, ttl_seconds=900, max_entries=512):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._store = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.time() > expires_at:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key, value):
        with self._lock:
            if len(self._store) >= self.max_entries:
                oldest = min(self._store, key=lambda k: self._store[k][1])
                self._store.pop(oldest, None)
            self._store[key] = (value, time.time() + self.ttl)

    def clear(self):
        with self._lock:
            self._store.clear()


history_cache = TTLCache(ttl_seconds=900, max_entries=256)
quote_cache = TTLCache(ttl_seconds=60, max_entries=512)
scan_cache = TTLCache(ttl_seconds=900, max_entries=64)
