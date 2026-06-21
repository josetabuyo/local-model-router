"""Ollama local provider (OpenAI-compatible endpoint)."""
import os
import time
import httpx

from benchmark.metrics import Result, local_cost_usd
from benchmark.tasks import Task

OLLAMA_BASE = "http://localhost:11434"


class OllamaProvider:
    name = "ollama"

    def list_models(self) -> list[str]:
        try:
            resp = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=10)
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            return []

    def unload(self, model_id: str) -> None:
        """Evict model from memory immediately after all its tasks finish."""
        try:
            httpx.post(
                f"{OLLAMA_BASE}/api/generate",
                json={"model": model_id, "keep_alive": 0},
                timeout=10,
            )
        except Exception:
            pass

    def run(self, model_id: str, task: Task) -> Result:
        num_thread = int(os.getenv("OLLAMA_NUM_THREAD", "4"))
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": task.prompt}],
            "stream": False,
            "options": {
                "num_predict": task.max_tokens,
                "num_thread": num_thread,   # cap CPU threads to leave headroom
            },
        }
        t0 = time.perf_counter()
        try:
            resp = httpx.post(
                f"{OLLAMA_BASE}/v1/chat/completions",
                json=payload,
                timeout=180,
            )
            data = resp.json()
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
                tokens_per_sec=tps, cost_usd=local_cost_usd(total_s),
                response=content,
            )
        except Exception as e:
            return Result(
                model_id=model_id, provider=self.name,
                task_id=task.id, task_name=task.name,
                ttft_s=None, total_s=time.perf_counter() - t0,
                prompt_tokens=0, output_tokens=0,
                tokens_per_sec=0.0, cost_usd=0.0, response="",
                error=str(e),
            )
