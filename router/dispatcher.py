"""Dispatches chat completion requests to the appropriate provider."""
import os

import httpx

OLLAMA_BASE = "http://localhost:11434"
GROQ_BASE = "https://api.groq.com/openai/v1"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"

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
        async with httpx.AsyncClient() as client:
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
