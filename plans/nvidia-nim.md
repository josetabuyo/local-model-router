# Plan: Explore Models via Nvidia NIM

**Written:** 2026-06-21  
**Status:** Pending — start when there is a concrete need (e.g. local `best:math` is not good enough for a real task).

---

## Why Nvidia NIM?

Nvidia NIM is a cloud inference platform with high-performance models (Llama 3.1 405B, Mistral, Phi-3, Nemotron, etc.) accessible via an OpenAI-compatible API. Compared to Groq and OpenRouter:

- Wider model catalog, including very large models (340B–405B)
- Phi-3 Medium ships with a **128k token context window** — relevant for long-context tasks
- Free credits on signup (~1000 calls), no subscription required
- The router already supports the OpenAI API contract — adding NIM is a matter of adding one provider method

---

## What to explore

### 1. Add `nvidia` as a provider in the router

```python
# router/dispatcher.py — add _call_nvidia()
NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"

async def _call_nvidia(self, model_id: str, payload: dict) -> dict:
    api_key = os.getenv("NVIDIA_API_KEY", "")
    if not api_key:
        raise ValueError("NVIDIA_API_KEY is not set")
    body = {**payload, "model": model_id}
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{NVIDIA_BASE}/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json()
```

New env var: `NVIDIA_API_KEY` — get it at [build.nvidia.com](https://build.nvidia.com).

### 2. Candidate models to benchmark

| NIM model | Interesting categories | Size |
|-----------|----------------------|------|
| `meta/llama-3.1-405b-instruct` | reasoning, math, context | 405B |
| `nvidia/nemotron-4-340b-instruct` | instruction, summarization | 340B |
| `mistralai/mistral-large-2-instruct` | coding, multilingual | ~123B |
| `microsoft/phi-3-medium-128k-instruct` | **long context (128k)**, coding | ~14B |
| `meta/codellama-70b-instruct` | coding, code_debug | 70B |

### 3. Benchmarks to run

Add `NimProvider` to `benchmark/providers/nim_provider.py` (copy `groq_provider.py` structure), then:

```bash
uv run run_benchmark.py --provider nvidia
```

Key comparison question: does `llama-3.1-405b` justify the latency and eventual cost over `qwen2.5:7b` locally?

### 4. Update `rankings/cloud.yaml`

Once NIM scores are recorded, add entries alongside Groq:

```yaml
  math:
    - provider: nvidia
      model: meta/llama-3.1-405b-instruct
      math_500: 95.0          # replace with measured score
      source: "NIM benchmark YYYY-MM-DD"
```

### 5. Special case: Phi-3 Medium — 128k context window

The current `context` benchmark task uses ~200 tokens, which is trivial for any model. A true long-context test would:

- Feed a full book, large codebase, or long transcript (~50k–100k tokens)
- Ask for retrieval of a specific detail buried in the middle
- Compare Phi-3 Medium (128k) vs deepseek-r1:8b (current local winner, ~8k practical context)

This is a separate benchmark category worth designing: `context_long`.

---

## Prerequisites

1. Create a free account at [build.nvidia.com](https://build.nvidia.com)
2. Obtain an API key (free credits available on signup)
3. Add `NVIDIA_API_KEY=...` to `.env`
4. Verify connectivity: `uv run python test_connection.py` (adapt for NIM endpoint)

---

## Benchmark policy note

Current policy: no live benchmark runs against cloud providers to avoid quota consumption. NIM free tier is limited (~1000 calls). Recommendation: run the full benchmark **once**, document results in `results/`, then populate `cloud.yaml`. Do not repeat unless testing a newly released model.
