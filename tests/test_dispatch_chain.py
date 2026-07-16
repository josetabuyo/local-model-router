"""Tests for _dispatch_chain empty-content fallback and _extract_content helper."""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from router.server import app, _extract_content

client = TestClient(app)


# ── _extract_content ──────────────────────────────────────────────────────────

def _choices(content):
    return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


def test_extract_content_normal():
    assert _extract_content(_choices("hello")) == "hello"


def test_extract_content_empty_string():
    assert _extract_content(_choices("")) == ""


def test_extract_content_none():
    assert _extract_content(_choices(None)) == ""


def test_extract_content_missing_choices():
    assert _extract_content({}) == ""


def test_extract_content_malformed():
    assert _extract_content({"choices": []}) == ""


# ── _dispatch_chain via POST /cloud/v1/chat/completions ───────────────────────
# Uses the /cloud endpoint with an explicit provider/model string so the registry
# resolves to a single-element chain (no fallback by ranking), then we control
# the dispatcher response via mocking.

GOOD_RESPONSE = {
    "choices": [{"message": {"content": "Villa Lugano"}, "finish_reason": "stop"}],
    "usage": {},
}
EMPTY_RESPONSE = {
    "choices": [{"message": {"content": ""}, "finish_reason": "stop"}],
    "usage": {},
}

PAYLOAD = {
    "model": "best:multilingual",
    "messages": [{"role": "user", "content": "¿De dónde sos?"}],
}


def test_dispatch_chain_returns_good_response():
    """Normal path: first provider returns content → accepted."""
    with patch("router.server.dispatcher.call", new=AsyncMock(return_value=GOOD_RESPONSE)):
        resp = client.post("/cloud/v1/chat/completions", json=PAYLOAD)
    assert resp.status_code == 200
    content = resp.json()["choices"][0]["message"]["content"]
    assert content == "Villa Lugano"
    assert resp.json()["x_router"]["fallback_used"] is False


def test_dispatch_chain_skips_empty_content_and_cascades():
    """First provider returns empty content → router falls through to next model."""
    call_count = 0

    async def side_effect(provider, model_id, payload, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return EMPTY_RESPONSE
        return GOOD_RESPONSE

    with patch("router.server.dispatcher.call", new=AsyncMock(side_effect=side_effect)):
        resp = client.post("/cloud/v1/chat/completions", json=PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert body["choices"][0]["message"]["content"] == "Villa Lugano"
    assert body["x_router"]["fallback_used"] is True
    # errors list must record the empty-content event
    assert any("empty content" in e for e in body["x_router"]["errors"])


def test_dispatch_chain_all_empty_returns_502():
    """All providers return empty content → 502 with errors list."""
    with patch("router.server.dispatcher.call", new=AsyncMock(return_value=EMPTY_RESPONSE)):
        resp = client.post("/cloud/v1/chat/completions", json=PAYLOAD)

    assert resp.status_code == 502
    body = resp.json()
    assert "errors" in body["detail"]
    assert all("empty content" in e for e in body["detail"]["errors"])


def test_dispatch_chain_http_error_still_cascades():
    """HTTP error on first provider still cascades (regression: existing behaviour)."""
    import httpx

    call_count = 0

    async def side_effect(provider, model_id, payload, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            mock_response = AsyncMock()
            mock_response.status_code = 429
            mock_response.text = "rate limited"
            raise httpx.HTTPStatusError("rate limited", request=None, response=mock_response)
        return GOOD_RESPONSE

    with patch("router.server.dispatcher.call", new=AsyncMock(side_effect=side_effect)):
        resp = client.post("/cloud/v1/chat/completions", json=PAYLOAD)

    assert resp.status_code == 200
    assert resp.json()["x_router"]["fallback_used"] is True


def test_dispatch_chain_value_error_cascades_not_aborts():
    """ValueError (e.g. missing API key) must cascade to next provider, not abort with 400."""
    call_count = 0

    async def side_effect(provider, model_id, payload, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("GROQ_API_KEY is not set")
        return GOOD_RESPONSE

    with patch("router.server.dispatcher.call", new=AsyncMock(side_effect=side_effect)):
        resp = client.post("/cloud/v1/chat/completions", json=PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert body["x_router"]["fallback_used"] is True
    assert any("GROQ_API_KEY" in e for e in body["x_router"]["errors"])


def test_dispatch_chain_uses_cascade_timeouts_for_multi_entry_chains():
    """Cascade chains pass per-provider timeout overrides; single-entry chains pass None."""
    from router.server import _CASCADE_TIMEOUTS

    recorded: list[float | None] = []

    async def side_effect(provider, model_id, payload, timeout=None):
        recorded.append(timeout)
        return GOOD_RESPONSE

    # Multi-entry chain (best:multilingual has several cloud models)
    with patch("router.server.dispatcher.call", new=AsyncMock(side_effect=side_effect)):
        resp = client.post("/cloud/v1/chat/completions", json=PAYLOAD)

    assert resp.status_code == 200
    assert recorded[0] is not None, "cascade chain must pass a timeout override"
    # The first entry is a groq model (speed-first reorder 2026-07-16)
    assert recorded[0] == _CASCADE_TIMEOUTS["groq"]


def test_dispatch_chain_no_timeout_override_for_single_entry():
    """Single explicit provider/model gets None timeout (uses dispatcher default, not cascade)."""
    recorded: list[float | None] = []

    async def side_effect(provider, model_id, payload, timeout=None):
        recorded.append(timeout)
        return GOOD_RESPONSE

    explicit_payload = {**PAYLOAD, "model": "groq/llama-3.1-8b-instant"}

    with patch("router.server.dispatcher.call", new=AsyncMock(side_effect=side_effect)):
        resp = client.post("/cloud/v1/chat/completions", json=explicit_payload)

    assert resp.status_code == 200
    assert len(recorded) == 1
    assert recorded[0] is None, "single-entry chain must not override timeout"


def test_hybrid_cloud_first_falls_back_to_local_on_cloud_failure():
    """cloud-first with all cloud providers failing must fall back to local (Pulpo repro)."""
    import httpx

    async def side_effect(provider, model_id, payload, timeout=None):
        if provider != "ollama":
            mock_response = AsyncMock()
            mock_response.status_code = 503
            mock_response.text = "service unavailable"
            raise httpx.HTTPStatusError("503", request=None, response=mock_response)
        return GOOD_RESPONSE

    with patch("router.server.dispatcher.call", new=AsyncMock(side_effect=side_effect)):
        resp = client.post(
            "/v1/chat/completions",
            json=PAYLOAD,
            headers={"X-Router-Strategy": "cloud-first"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["x_router"]["fallback_used"] is True
    assert body["x_router"]["resolved"].startswith("ollama/")
