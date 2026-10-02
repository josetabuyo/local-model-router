"""Ollama dispatch: native /api/chat with think=false by default, /v1 when OpenAI-only features are used."""
import json
import os
from unittest.mock import patch

import httpx
import pytest

from router import dispatcher as d

NATIVE = {"model": "qwen3.5:9b", "message": {"role": "assistant", "content": "51", "thinking": ""},
          "done": True, "done_reason": "stop", "prompt_eval_count": 20, "eval_count": 2}


def test_ollama_chat_to_openai_shape():
    out = d.ollama_chat_to_openai(NATIVE, "qwen3.5:9b")
    assert out["object"] == "chat.completion" and out["model"] == "qwen3.5:9b"
    assert out["choices"][0]["message"] == {"role": "assistant", "content": "51"}
    assert out["choices"][0]["finish_reason"] == "stop"
    assert out["usage"] == {"prompt_tokens": 20, "completion_tokens": 2, "total_tokens": 22}
    assert d.ollama_chat_to_openai({**NATIVE, "done_reason": "length"}, "m")["choices"][0]["finish_reason"] == "length"


@pytest.mark.parametrize("env,expected", [
    ({}, False), ({"OLLAMA_THINK": "false"}, False), ({"OLLAMA_THINK": "true"}, True),
    ({"OLLAMA_THINK": "model"}, None), ({"OLLAMA_THINK": ""}, None),
])
def test_ollama_think_env(env, expected):
    with patch.dict(os.environ, env, clear=False):
        if "OLLAMA_THINK" not in env:
            os.environ.pop("OLLAMA_THINK", None)
        assert d._ollama_think() is expected


def _transport(seen: list):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, json.loads(request.content)))
        if request.url.path == "/api/chat":
            return httpx.Response(200, json=NATIVE)
        return httpx.Response(200, json={"choices": [{"message": {"content": "v1"}, "finish_reason": "stop"}], "usage": {}})
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_plain_chat_uses_native_endpoint_with_think_false():
    seen: list = []
    real_client = httpx.AsyncClient
    with patch.dict(os.environ, {"OLLAMA_THINK": "false"}), \
         patch("router.dispatcher.httpx.AsyncClient", lambda **kw: real_client(transport=_transport(seen), **kw)):
        out = await d.Dispatcher().call("ollama", "qwen3.5:9b", {"messages": [{"role": "user", "content": "17*3?"}], "max_tokens": 50, "temperature": 0})
    path, body = seen[0]
    assert path == "/api/chat"
    assert body["think"] is False and body["stream"] is False
    assert body["options"] == {"num_predict": 50, "temperature": 0}
    assert out["choices"][0]["message"]["content"] == "51"


@pytest.mark.asyncio
async def test_tools_request_keeps_openai_endpoint():
    seen: list = []
    real_client = httpx.AsyncClient
    with patch.dict(os.environ, {"OLLAMA_THINK": "false"}), \
         patch("router.dispatcher.httpx.AsyncClient", lambda **kw: real_client(transport=_transport(seen), **kw)):
        out = await d.Dispatcher().call("ollama", "qwen3.5:9b", {"messages": [], "tools": [{"type": "function", "function": {"name": "f"}}]})
    assert seen[0][0] == "/v1/chat/completions" and "think" not in seen[0][1]
    assert out["choices"][0]["message"]["content"] == "v1"


@pytest.mark.asyncio
async def test_think_model_default_keeps_openai_endpoint():
    seen: list = []
    real_client = httpx.AsyncClient
    with patch.dict(os.environ, {"OLLAMA_THINK": "model"}), \
         patch("router.dispatcher.httpx.AsyncClient", lambda **kw: real_client(transport=_transport(seen), **kw)):
        await d.Dispatcher().call("ollama", "qwen2.5:7b", {"messages": []})
    assert seen[0][0] == "/v1/chat/completions"
