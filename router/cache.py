"""Bounded, TTL-based response cache for 'best:<category>' requests.

Goal: cut repeated spend on identical benchmark/test calls without risking
unbounded memory growth. Two independent bounds keep it safe under load:

  - CACHE_TTL_SECONDS   (default 86400 / 1 day) — entries expire regardless
                          of traffic volume.
  - CACHE_MAX_ENTRIES   (default 500)           — hard cap on entry count;
                          oldest entry is evicted first (LRU) once full.

500 entries * ~5KB average chat-completion response ≈ 2.5MB resident — a
non-issue for a single-process router. Only 'best:<category>' requests are
cached: explicit provider/model calls (e.g. 'ollama/qwen2.5:7b') are assumed
intentional and always dispatched live.
"""
import hashlib
import json
import os
import time
from collections import OrderedDict

CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() not in ("0", "false", "no")
CACHE_TTL_SECONDS = float(os.getenv("CACHE_TTL_SECONDS", 86400))
CACHE_MAX_ENTRIES = int(os.getenv("CACHE_MAX_ENTRIES", 500))


def make_key(endpoint: str, strategy: str, requested: str, payload: dict) -> str:
    """Deterministic cache key from the request shape (order-independent)."""
    payload_json = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    return f"{endpoint}:{strategy}:{requested}:{digest}"


class ResponseCache:
    """In-memory LRU cache with per-entry TTL. Not thread-safe across
    processes (each router worker holds its own) — fine for this single
    -process deployment; revisit with a shared store if that changes."""

    def __init__(self, max_entries: int = CACHE_MAX_ENTRIES, ttl_seconds: float = CACHE_TTL_SECONDS):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._store: OrderedDict[str, tuple[float, dict]] = OrderedDict()

    def get(self, key: str) -> dict | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, result = entry
        if time.time() >= expires_at:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return result

    def set(self, key: str, result: dict) -> None:
        self._store[key] = (time.time() + self.ttl_seconds, result)
        self._store.move_to_end(key)
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def stats(self) -> dict:
        return {
            "enabled": CACHE_ENABLED,
            "entries": len(self._store),
            "max_entries": self.max_entries,
            "ttl_seconds": self.ttl_seconds,
        }

    def clear(self) -> None:
        self._store.clear()
