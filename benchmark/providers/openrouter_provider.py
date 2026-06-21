"""OpenRouter provider — access to many free open-source models."""
import time
import os
import httpx

MAX_RETRIES = 3

from benchmark.metrics import Result, cloud_cost_usd
from benchmark.tasks import Task

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

FREE_MODELS = [
    "google/gemma-4-31b-it:free",
    "openai/gpt-oss-20b:free",
    "nvidia/nemotron-nano-9b-v2:free",
]


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")

    def list_models(self) -> list[str]:
        return FREE_MODELS

    def run(self, model_id: str, task: Task) -> Result:
        if not self.api_key:
            return Result(
                model_id=model_id, provider=self.name,
                task_id=task.id, task_name=task.name,
                ttft_s=None, total_s=0, prompt_tokens=0, output_tokens=0,
                tokens_per_sec=0, cost_usd=0, response="",
                error="OPENROUTER_API_KEY not set",
            )

        t0 = time.perf_counter()
        try:
            data = None
            for attempt in range(MAX_RETRIES):
                resp = httpx.post(
                    f"{OPENROUTER_BASE}/chat/completions",
                    json={
                        "model": model_id,
                        "messages": [{"role": "user", "content": task.prompt}],
                        "max_tokens": task.max_tokens,
                    },
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "HTTP-Referer": "https://github.com/local-models-benchmark",
                        "X-Title": "LocalModelsBenchmark",
                    },
                    timeout=90,
                )
                data = resp.json()
                if "error" not in data:
                    break
                err = data["error"]
                # surface the upstream detail, not the generic wrapper
                raw = err.get("metadata", {}).get("raw", "")
                msg = raw or err.get("message", str(err))
                retry_after = err.get("metadata", {}).get("retry_after_seconds", 30)
                if err.get("code") == 429 and attempt < MAX_RETRIES - 1:
                    time.sleep(retry_after)
                    continue
                raise ValueError(msg)
            total_s = time.perf_counter() - t0

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
                cost_usd=cloud_cost_usd(f"openrouter/{model_id}", prompt_tokens + output_tokens),
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
