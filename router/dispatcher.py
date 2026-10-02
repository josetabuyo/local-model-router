"""Dispatches chat completion requests to the appropriate provider."""
import os
import time
import uuid

import httpx

OLLAMA_BASE = "http://localhost:11434"
GROQ_BASE = "https://api.groq.com/openai/v1"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"

# Ollama thinking control. Ollama's OpenAI-compatible /v1/chat/completions
# IGNORES "think": false (verified 2026-10-02 on 0.35.0: qwen3.5:9b still emitted
# a 200-token reasoning trace), so plain chat requests go through the native
# /api/chat endpoint with "think" set from OLLAMA_THINK (default off — a
# 7-9B thinking model spends 30-130s per trivial task otherwise, see
# rankings/local.yaml). Requests that need OpenAI-only features (tools,
# response_format) keep using /v1 untouched. OLLAMA_THINK=true restores the
# model default; OLLAMA_THINK=model also leaves it to the model.
_OPENAI_ONLY_KEYS = ("tools", "tool_choice", "response_format", "functions")


def _ollama_think() -> bool | None:
    v = os.getenv("OLLAMA_THINK", "false").strip().lower()
    if v in ("", "model", "default"):
        return None
    return v in ("1", "true", "yes", "on")


def ollama_chat_to_openai(data: dict, model_id: str) -> dict:
    """Map a native /api/chat response onto the chat.completion shape the cascade expects."""
    message = data.get("message", {}) or {}
    prompt_tokens = int(data.get("prompt_eval_count", 0) or 0)
    completion_tokens = int(data.get("eval_count", 0) or 0)
    done_reason = data.get("done_reason") or "stop"
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_id,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": message.get("content", "") or ""},
            "finish_reason": "length" if done_reason == "length" else "stop",
        }],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


# Models that hang without explicit thinking=off. Client payload wins if it sets chat_template_kwargs.
# DeepSeek V4 family and Kimi K2 use {"thinking": false}; Qwen3.5 uses {"enable_thinking": false}.
_NVIDIA_THINKING_DEFAULTS: dict[str, dict] = {}


class Dispatcher:
    async def call(self, provider: str, model_id: str, payload: dict, timeout: float | None = None) -> dict:
        if provider == "ollama":
            return await self._call_ollama(model_id, payload, timeout=timeout or 300.0)
        if provider == "groq":
            return await self._call_groq(model_id, payload, timeout=timeout or 60.0)
        if provider == "openrouter":
            return await self._call_openrouter(model_id, payload, timeout=timeout or 120.0)
        if provider == "nvidia":
            return await self._call_nvidia(model_id, payload, timeout=timeout or 120.0)
        if provider == "gemini":
            return await self._call_gemini(model_id, payload, timeout=timeout or 60.0)
        raise ValueError(f"Unknown provider '{provider}'")

    async def _call_ollama(self, model_id: str, payload: dict, timeout: float = 300.0) -> dict:
        body = {**payload, "model": model_id, "stream": False}
        # Ollama's /v1 endpoint accepts max_tokens but also options.num_predict
        # Pass max_tokens via options to honour the thread cap from the benchmark harness
        if "max_tokens" in body:
            body.setdefault("options", {})["num_predict"] = body.pop("max_tokens")
        think = _ollama_think()
        native = think is not None and not any(k in body for k in _OPENAI_ONLY_KEYS)
        async with httpx.AsyncClient() as client:
            if native:
                # OpenAI sampling params live under "options" on the native endpoint.
                for k in ("temperature", "top_p", "seed", "stop"):
                    if k in body:
                        body.setdefault("options", {})[k] = body.pop(k)
                body["think"] = think
                resp = await client.post(f"{OLLAMA_BASE}/api/chat", json=body, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
                if "error" in data:
                    raise ValueError(f"ollama: {data['error']}")
                return ollama_chat_to_openai(data, model_id)
            resp = await client.post(
                f"{OLLAMA_BASE}/v1/chat/completions",
                json=body,
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()

    async def _call_groq(self, model_id: str, payload: dict, timeout: float = 60.0) -> dict:
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set")
        body = {**payload, "model": model_id}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GROQ_BASE}/chat/completions",
                json=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "local-model-router/1.0",
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()

    async def _call_openrouter(self, model_id: str, payload: dict, timeout: float = 120.0) -> dict:
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set")
        body = {**payload, "model": model_id}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{OPENROUTER_BASE}/chat/completions",
                json=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "local-model-router/1.0",
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()

    async def _call_gemini(self, model_id: str, payload: dict, timeout: float = 60.0) -> dict:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        body = {**payload, "model": model_id}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GEMINI_BASE}/chat/completions",
                json=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "local-model-router/1.0",
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()

    async def _call_nvidia(self, model_id: str, payload: dict, timeout: float = 120.0) -> dict:
        api_key = os.getenv("NVIDIA_API_KEY", "")
        if not api_key:
            raise ValueError("NVIDIA_API_KEY is not set")
        body = {**payload, "model": model_id}
        if model_id in _NVIDIA_THINKING_DEFAULTS and "chat_template_kwargs" not in body:
            body["chat_template_kwargs"] = _NVIDIA_THINKING_DEFAULTS[model_id]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{NVIDIA_BASE}/chat/completions",
                json=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "local-model-router/1.0",
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
