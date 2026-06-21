"""Groq cloud provider — free tier, very fast inference."""
import time
import os
import httpx

from benchmark.metrics import Result, cloud_cost_usd
from benchmark.tasks import Task

GROQ_API_BASE = "https://api.groq.com/openai/v1"

FREE_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
]


class GroqProvider:
    name = "groq"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")

    def list_models(self) -> list[str]:
        return FREE_MODELS

    def run(self, model_id: str, task: Task) -> Result:
        if not self.api_key:
            return Result(
                model_id=model_id, provider=self.name,
                task_id=task.id, task_name=task.name,
                ttft_s=None, total_s=0, prompt_tokens=0, output_tokens=0,
                tokens_per_sec=0, cost_usd=0, response="",
                error="GROQ_API_KEY not set",
            )

        t0 = time.perf_counter()
        try:
            resp = httpx.post(
                f"{GROQ_API_BASE}/chat/completions",
                json={
                    "model": model_id,
                    "messages": [{"role": "user", "content": task.prompt}],
                    "max_tokens": task.max_tokens,
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "User-Agent": "local-models-benchmark/1.0",
                },
                timeout=60,
            )
            data = resp.json()
            total_s = time.perf_counter() - t0

            if "error" in data:
                raise ValueError(data["error"].get("message", str(data["error"])))

            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            tps = output_tokens / total_s if total_s > 0 else 0.0

            return Result(
                model_id=model_id, provider=self.name,
                task_id=task.id, task_name=task.name,
                ttft_s=None, total_s=total_s,
                prompt_tokens=prompt_tokens, output_tokens=output_tokens,
                tokens_per_sec=tps,
                cost_usd=cloud_cost_usd(f"groq/{model_id}", prompt_tokens + output_tokens),
                response=content,
            )
        except Exception as e:
            return Result(
                model_id=model_id, provider=self.name,
                task_id=task.id, task_name=task.name,
                ttft_s=None, total_s=time.perf_counter() - t0,
                prompt_tokens=0, output_tokens=0,
                tokens_per_sec=0, cost_usd=0, response="",
                error=str(e),
            )
