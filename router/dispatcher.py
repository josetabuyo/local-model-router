"""Dispatches chat completion requests to the appropriate provider."""
import os

import httpx

OLLAMA_BASE = "http://localhost:11434"
GROQ_BASE = "https://api.groq.com/openai/v1"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"


class Dispatcher:
    async def call(self, provider: str, model_id: str, payload: dict) -> dict:
        if provider == "ollama":
            return await self._call_ollama(model_id, payload)
        if provider == "groq":
            return await self._call_groq(model_id, payload)
        if provider == "openrouter":
            return await self._call_openrouter(model_id, payload)
        raise ValueError(f"Unknown provider '{provider}'")

    async def _call_ollama(self, model_id: str, payload: dict) -> dict:
        body = {**payload, "model": model_id, "stream": False}
        # Ollama's /v1 endpoint accepts max_tokens but also options.num_predict
        # Pass max_tokens via options to honour the thread cap from the benchmark harness
        if "max_tokens" in body:
            body.setdefault("options", {})["num_predict"] = body.pop("max_tokens")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{OLLAMA_BASE}/v1/chat/completions",
                json=body,
                timeout=300.0,
            )
            resp.raise_for_status()
            return resp.json()

    async def _call_groq(self, model_id: str, payload: dict) -> dict:
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
                timeout=60.0,
            )
            resp.raise_for_status()
            return resp.json()

    async def _call_openrouter(self, model_id: str, payload: dict) -> dict:
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
                timeout=120.0,
            )
            resp.raise_for_status()
            return resp.json()
