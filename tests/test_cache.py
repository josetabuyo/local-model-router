"""Tests for the bounded TTL cache on 'best:<category>' requests."""
import time
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from router.cache import ResponseCache, make_key
from router.server import app

client = TestClient(app)

GOOD_RESPONSE = {
    "choices": [{"message": {"content": "Villa Lugano"}, "finish_reason": "stop"}],
    "usage": {},
}

BEST_PAYLOAD = {
    "model": "best:multilingual",
    "messages": [{"role": "user", "content": "¿De dónde sos?"}],
}

EXPLICIT_PAYLOAD = {
    "model": "groq/llama-3.1-8b-instant",
    "messages": [{"role": "user", "content": "¿De dónde sos?"}],
}


# ── ResponseCache unit tests ──────────────────────────────────────────────────


def test_cache_set_and_get_roundtrip():
    cache = ResponseCache(max_entries=10, ttl_seconds=60)
    key = make_key("cloud", "cloud-only", "best:multilingual", BEST_PAYLOAD)
    cache.set(key, GOOD_RESPONSE)
    assert cache.get(key) == GOOD_RESPONSE


def test_cache_miss_returns_none():
    cache = ResponseCache(max_entries=10, ttl_seconds=60)
    assert cache.get("nonexistent") is None


def test_cache_expires_after_ttl():
    cache = ResponseCache(max_entries=10, ttl_seconds=0.05)
    key = "k"
    cache.set(key, GOOD_RESPONSE)
    assert cache.get(key) == GOOD_RESPONSE
    time.sleep(0.1)
    assert cache.get(key) is None


def test_cache_evicts_oldest_when_over_capacity():
    cache = ResponseCache(max_entries=2, ttl_seconds=60)
    cache.set("a", {"v": 1})
    cache.set("b", {"v": 2})
    cache.set("c", {"v": 3})
    assert cache.get("a") is None
    assert cache.get("b") == {"v": 2}
    assert cache.get("c") == {"v": 3}


def test_cache_get_refreshes_lru_order():
    cache = ResponseCache(max_entries=2, ttl_seconds=60)
    cache.set("a", {"v": 1})
    cache.set("b", {"v": 2})
    cache.get("a")  # touch 'a' so 'b' becomes the oldest
    cache.set("c", {"v": 3})
    assert cache.get("a") == {"v": 1}
    assert cache.get("b") is None
    assert cache.get("c") == {"v": 3}


def test_make_key_is_order_independent_for_payload_keys():
    payload_a = {"model": "best:x", "messages": [{"role": "user", "content": "hi"}], "temperature": 0.5}
    payload_b = {"temperature": 0.5, "messages": [{"role": "user", "content": "hi"}], "model": "best:x"}
    assert make_key("cloud", "cloud-only", "best:x", payload_a) == make_key("cloud", "cloud-only", "best:x", payload_b)


def test_make_key_differs_on_content():
    payload_a = {"messages": [{"role": "user", "content": "hi"}]}
    payload_b = {"messages": [{"role": "user", "content": "bye"}]}
    assert make_key("cloud", "cloud-only", "best:x", payload_a) != make_key("cloud", "cloud-only", "best:x", payload_b)


# ── Integration: caching only applies to 'best:<category>' requests ──────────


def test_repeated_best_request_hits_cache_second_call():
    """Second identical best:<category> call must not hit the dispatcher."""
    with patch("router.server.dispatcher.call", new=AsyncMock(return_value=GOOD_RESPONSE)) as mock_call:
        first = client.post("/cloud/v1/chat/completions", json=BEST_PAYLOAD)
        second = client.post("/cloud/v1/chat/completions", json=BEST_PAYLOAD)

    assert first.status_code == 200
    assert second.status_code == 200
    assert mock_call.call_count == 1, "second identical request should be served from cache"
    assert first.json()["x_router"]["cached"] is False
    assert second.json()["x_router"]["cached"] is True
    assert second.json()["choices"][0]["message"]["content"] == "Villa Lugano"


def test_explicit_provider_model_requests_are_never_cached():
    """Explicit provider/model requests always dispatch live, no caching."""
    with patch("router.server.dispatcher.call", new=AsyncMock(return_value=GOOD_RESPONSE)) as mock_call:
        first = client.post("/cloud/v1/chat/completions", json=EXPLICIT_PAYLOAD)
        second = client.post("/cloud/v1/chat/completions", json=EXPLICIT_PAYLOAD)

    assert mock_call.call_count == 2, "explicit provider/model calls must not be cached"
    assert first.json()["x_router"]["cached"] is False
    assert second.json()["x_router"]["cached"] is False


def test_different_messages_do_not_share_cache_entry():
    """Different message content under the same category must not collide."""
    payload_2 = {**BEST_PAYLOAD, "messages": [{"role": "user", "content": "different question"}]}

    with patch("router.server.dispatcher.call", new=AsyncMock(return_value=GOOD_RESPONSE)) as mock_call:
        client.post("/cloud/v1/chat/completions", json=BEST_PAYLOAD)
        client.post("/cloud/v1/chat/completions", json=payload_2)

    assert mock_call.call_count == 2


def test_cache_stats_endpoint():
    resp = client.get("/v1/router/cache")
    assert resp.status_code == 200
    body = resp.json()
    assert "entries" in body and "max_entries" in body and "ttl_seconds" in body
