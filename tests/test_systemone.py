"""Tests for POST /v1/systemone — validation, Jev provider cascade, emulation."""
import json
import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from router import systemone
from router.server import app

client = TestClient(app)

QUESTIONS = {
    "department": {
        "type": "choice",
        "instructions": "Which team should handle this",
        "criteria": {"billing": "Payment issues", "technical": "Bugs", "sales": "Pricing"},
    },
    "frustration": {
        "type": "score",
        "instructions": "How frustrated the customer appears",
        "criteria": ["Calm", "Frustrated but civil", "Very angry"],
    },
    "is_urgent": {"type": "noul", "instructions": "The message conveys urgency"},
}
BODY = {"state": "My Stripe integration keeps failing and I'm losing sales. Help ASAP.", "questions": QUESTIONS}

JEV_RESPONSE = {
    "model": "jev-1.13.0",
    "answers": {
        "department": {"type": "choice", "choice": "technical", "confidence": 0.78, "probabilities": {}},
        "frustration": {"type": "score", "score": 1.0, "confidence": 1.0, "legend": {}, "probabilities": {}},
        "is_urgent": {"type": "noul", "noul": 1.0},
    },
    "usage": {"input_tokens": 392, "output_tokens": 65},
}

EMULATED_JSON = json.dumps({
    "department": {"choice": "technical", "confidence": 0.9},
    "frustration": {"score": 1, "confidence": 0.7},
    "is_urgent": 0.95,
})


def _chat(content):
    return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}], "usage": {}}


def _http_error(status: int, text: str = "err") -> httpx.HTTPStatusError:
    req = httpx.Request("POST", "https://x/systemone")
    return httpx.HTTPStatusError("boom", request=req, response=httpx.Response(status, text=text, request=req))


# ── validate ──────────────────────────────────────────────────────────────────


def test_validate_ok():
    state, qs = systemone.validate(BODY)
    assert state.startswith("My Stripe") and set(qs) == {"department", "frustration", "is_urgent"}


@pytest.mark.parametrize("bad", [
    {"questions": QUESTIONS},                                                   # no state
    {"state": "x", "questions": {}},                                            # empty questions
    {"state": "x", "questions": {"q": {"type": "text", "instructions": "i"}}},  # bad type
    {"state": "x", "questions": {"q": {"type": "noul"}}},                       # no instructions
    {"state": "x", "questions": {"q": {"type": "choice", "instructions": "i", "criteria": {"a": "A"}}}},
    {"state": "x", "questions": {"q": {"type": "score", "instructions": "i", "criteria": {"a": "A"}}}},
])
def test_validate_rejects(bad):
    with pytest.raises(ValueError):
        systemone.validate(bad)


def test_endpoint_400_on_invalid_body():
    resp = client.post("/v1/systemone", json={"state": "x", "questions": []})
    assert resp.status_code == 400
    assert "questions" in resp.json()["detail"]


# ── real provider cascade ─────────────────────────────────────────────────────


def test_typesafe_first_when_key_set():
    with patch.dict(os.environ, {"TYPESAFE_API_KEY": "ts", "OPENROUTER_API_KEY": "or"}), \
         patch("router.systemone.call_jev", new=AsyncMock(return_value=dict(JEV_RESPONSE))) as call:
        resp = client.post("/v1/systemone", json=BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert body["x_router"] == {"endpoint": "systemone", "resolved": "typesafe/jev-latest",
                                "strategy": "jev", "emulated": False, "fallback_used": False}
    assert body["answers"]["department"]["choice"] == "technical"
    assert call.await_args.args[:2] == ("typesafe", "jev-latest")


def test_openrouter_fallback_when_typesafe_fails():
    async def fake(provider, model, state, questions, timeout=30.0):
        if provider == "typesafe":
            raise _http_error(401, "bad key")
        return dict(JEV_RESPONSE)
    with patch.dict(os.environ, {"TYPESAFE_API_KEY": "ts", "OPENROUTER_API_KEY": "or"}), \
         patch("router.systemone.call_jev", new=fake):
        resp = client.post("/v1/systemone", json=BODY)
    body = resp.json()
    assert resp.status_code == 200
    assert body["x_router"]["resolved"] == "openrouter/jev-1.13"
    assert body["x_router"]["fallback_used"] is True
    assert body["x_router"]["errors"][0].startswith("typesafe/jev-latest: HTTP 401")


def test_model_override_is_forwarded():
    with patch.dict(os.environ, {"TYPESAFE_API_KEY": "ts"}), \
         patch("router.systemone.call_jev", new=AsyncMock(return_value=dict(JEV_RESPONSE))) as call:
        client.post("/v1/systemone", json={**BODY, "model": "jev-1.13"})
    assert call.await_args.args[1] == "jev-1.13"


def test_jev_only_returns_502_when_all_fail():
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or"}), \
         patch("router.systemone.call_jev", new=AsyncMock(side_effect=_http_error(403, "Key limit exceeded"))):
        resp = client.post("/v1/systemone", json=BODY, headers={"X-Router-Strategy": "jev-only"})
    assert resp.status_code == 502
    assert "Key limit exceeded" in json.dumps(resp.json())


def test_no_provider_and_fallback_disabled_is_502():
    env = {"JEV_EMULATE_FALLBACK": "false"}
    with patch.dict(os.environ, env), patch("router.systemone.provider_chain", return_value=[]):
        resp = client.post("/v1/systemone", json=BODY)
    assert resp.status_code == 502
    assert "no System One provider configured" in json.dumps(resp.json())


# ── emulation ─────────────────────────────────────────────────────────────────


def test_emulate_strategy_uses_chat_cascade():
    with patch("router.server.dispatcher.call", new=AsyncMock(return_value=_chat(EMULATED_JSON))) as call, \
         patch("router.systemone.call_jev", new=AsyncMock()) as jev:
        resp = client.post("/v1/systemone", json=BODY, headers={"X-Router-Strategy": "emulate"})
    assert resp.status_code == 200
    body = resp.json()
    assert jev.await_count == 0
    assert body["x_router"]["emulated"] is True and body["x_router"]["fallback_used"] is False
    assert body["answers"]["department"] == {
        "type": "choice", "choice": "technical", "confidence": 0.9,
        "probabilities": {"billing": pytest.approx(0.05), "technical": 0.9, "sales": pytest.approx(0.05)},
    }
    assert body["answers"]["frustration"]["score"] == 1.0
    assert body["answers"]["frustration"]["legend"]["1"] == "Frustrated but civil"
    assert body["answers"]["is_urgent"] == {"type": "noul", "noul": 0.95}
    # the chat cascade was asked for JSON with all three question names
    sent = call.await_args.args[2]["messages"][1]["content"]
    assert all(name in sent for name in QUESTIONS)


def test_falls_back_to_emulation_when_jev_fails():
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or"}), \
         patch("router.systemone.call_jev", new=AsyncMock(side_effect=_http_error(403, "Key limit exceeded"))), \
         patch("router.server.dispatcher.call", new=AsyncMock(return_value=_chat("```json\n" + EMULATED_JSON + "\n```"))):
        resp = client.post("/v1/systemone", json=BODY)
    body = resp.json()
    assert resp.status_code == 200
    assert body["x_router"]["emulated"] is True and body["x_router"]["fallback_used"] is True
    assert body["x_router"]["errors"][0].startswith("openrouter/jev-1.13: HTTP 403")


def test_emulation_skips_model_with_bad_json():
    outputs = [_chat("I think it's technical, not sure."), _chat(EMULATED_JSON)]
    with patch("router.server.dispatcher.call", new=AsyncMock(side_effect=outputs)):
        resp = client.post("/v1/systemone", json=BODY, headers={"X-Router-Strategy": "emulate"})
    assert resp.status_code == 200
    assert resp.json()["answers"]["is_urgent"]["noul"] == 0.95
    assert any("no JSON object" in e for e in resp.json()["x_router"]["errors"])


def test_parse_emulation_rejects_unknown_choice():
    with pytest.raises(ValueError):
        systemone.parse_emulation(json.dumps({"department": "legal", "frustration": 0, "is_urgent": 1}), QUESTIONS)


def test_parse_emulation_rejects_score_out_of_range():
    with pytest.raises(ValueError):
        systemone.parse_emulation(json.dumps({"department": "billing", "frustration": 7, "is_urgent": 1}), QUESTIONS)
