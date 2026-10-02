"""Ollama local provider (native /api/chat endpoint).

Thinking models (qwen3.x, deepseek-r1, gemma-4 thinking variants) emit a long
reasoning trace before the answer. The harness measures wall clock, so that
trace dominates every "trivial" task. `think` controls it:
  None  — model default (thinking ON for thinking models)   → `--think` / default
  False — disabled (`think: false` on /api/chat)             → `--no-think`
The setting is recorded in Result.extra["think"] so rankings can say which
mode a number came from. Non-thinking models ignore the flag.
"""
import os
import time
import httpx

from benchmark.metrics import Result, local_cost_usd
from benchmark.tasks import Task

OLLAMA_BASE = "http://localhost:11434"


class OllamaProvider:
    name = "ollama"

    def __init__(self, think: bool | None = None):
        self.think = think

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
        if self.think is not None:
            payload["think"] = self.think
        t0 = time.perf_counter()
        try:
            resp = httpx.post(
                f"{OLLAMA_BASE}/api/chat",
                json=payload,
                timeout=180,
            )
            data = resp.json()
            total_s = time.perf_counter() - t0
            if "error" in data:
                raise ValueError(data["error"])

            message = data.get("message", {})
            content = message.get("content", "") or ""
            thinking = message.get("thinking") or ""
            prompt_tokens = data.get("prompt_eval_count", 0)
            output_tokens = data.get("eval_count", 0)   # includes thinking tokens
            tps = output_tokens / total_s if total_s > 0 else 0.0

            return Result(
                model_id=model_id, provider=self.name,
                task_id=task.id, task_name=task.name,
                ttft_s=None, total_s=total_s,
                prompt_tokens=prompt_tokens, output_tokens=output_tokens,
                tokens_per_sec=tps, cost_usd=local_cost_usd(total_s),
                response=content,
                extra={"think": self.think, "thinking_chars": len(thinking)},
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
