# local-model-router

An OpenAI-compatible HTTP proxy that routes requests to the **best available LLM** — local (Ollama) or cloud (Groq, OpenRouter) — based on per-category benchmarks you own and control.

```bash
# ask for the best model for coding — router decides, you don't change a line of code
curl http://localhost:11435/local/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "best:coding", "messages": [{"role": "user", "content": "Write a binary search in Python."}]}'
```

---

## Why

Running LLMs locally is free and private. Cloud models are faster and stronger. Most tools make you pick one. This router lets you use both through a single OpenAI-compatible endpoint, with rankings you built from your own benchmarks.

**Key properties:**
- Drop-in replacement for the OpenAI API — no code changes in your apps
- Three endpoint families: local-only, cloud-only, hybrid with fallback
- Rankings are YAML files in the repo — you control who's "best"
- Local is always preferred over cloud when scores are equivalent (cost $0 vs latency)

---

## Architecture

```
your app  →  local-model-router (port 11435)
                     │
          ┌──────────┼──────────┐
          │          │          │
      /local      /cloud      /v1
     (Ollama)   (Groq etc)  (hybrid)
          │          │          │
      rankings/  rankings/  tries both
      local.yaml cloud.yaml in order
```

```
router/
├── server.py       FastAPI app — three endpoint families
├── registry.py     loads rankings, resolves "best:coding" → (provider, model_id)
└── dispatcher.py   makes the actual HTTP call to Ollama / Groq / OpenRouter

rankings/
├── local.yaml      per-category rankings from own benchmark runs
└── cloud.yaml      per-category rankings from public benchmarks (no live calls)

benchmark/          harness for running your own benchmarks
plans/              roadmap notes (e.g. Nvidia NIM integration)
results/            raw benchmark JSON — historical record
```

---

## Supported Models

### Local — Ollama

Models currently installed and ranked:

| Model | Size | Speed (avg) | Top categories |
|-------|------|-------------|----------------|
| `qwen2.5:7b` | 4.7 GB | ~22 tok/s | reasoning, coding, math, summarization, instruction, multilingual, code_debug |
| `deepseek-r1:8b` | 5.2 GB | ~20 tok/s | context |

Models tested and removed (not competitive enough to justify disk space):

| Model | Size | Why removed |
|-------|------|-------------|
| `qwen2.5:14b` | 9.0 GB | ~7 tok/s average — 3× slower than `qwen2.5:7b` with no quality advantage |

### Cloud

| Model | Provider | Speed | Notes |
|-------|----------|-------|-------|
| `llama-3.3-70b-versatile` | Groq | ~185 tok/s | Top cloud model across all categories |
| `llama-3.1-8b-instant` | Groq | ~206 tok/s | Faster but weaker quality |

---

## Benchmark Results

Own benchmark run — 2026-06-20 · Apple Silicon Mac · 8 categories.

### Tokens per second

| Model | Provider | reasoning | coding | math | summarization | instruction | multilingual | code_debug | context |
|-------|----------|-----------|--------|------|---------------|-------------|--------------|------------|---------|
| `qwen2.5:7b` | Ollama | 18.0 | 24.1 | 25.6 | 21.7 | 20.4 | 22.7 | 21.8 | 16.1 |
| `deepseek-r1:8b` | Ollama | 18.9† | 21.7 | 21.5 | 21.3 | 21.9 | 21.9 | 21.3 | 19.2 |
| `qwen2.5:14b` | Ollama | 4.6 | 8.8 | 7.0 | 9.0 | 8.2 | 6.1 | 7.0 | 1.4 |
| `llama-3.3-70b-versatile` | Groq | 119.2 | 169.6 | 346.4 | 102.8 | 15.1 | 106.8 | 216.3 | 91.2 |
| `llama-3.1-8b-instant` | Groq | 298.6 | 292.6 | 79.4 | 124.1 | 60.6 | 152.3 | 262.2 | 72.9 |

† `deepseek-r1:8b` generates 3000+ chain-of-thought tokens for reasoning tasks → 164s wall clock vs 19s for `qwen2.5:7b` despite similar tok/s.

### Category winners

| Category | Local best | Cloud best |
|----------|-----------|-----------|
| reasoning | **qwen2.5:7b** | llama-3.3-70b-versatile |
| coding | **qwen2.5:7b** | llama-3.3-70b-versatile |
| math | **qwen2.5:7b** | llama-3.3-70b-versatile |
| summarization | **qwen2.5:7b** | llama-3.3-70b-versatile |
| instruction | **qwen2.5:7b** | llama-3.3-70b-versatile |
| multilingual | **qwen2.5:7b** | llama-3.3-70b-versatile |
| code_debug | **qwen2.5:7b** | llama-3.3-70b-versatile |
| context | **deepseek-r1:8b** ¹ | llama-3.3-70b-versatile |

¹ `deepseek-r1:8b` correctly retrieved a specific detail from a multi-turn conversation. `qwen2.5:7b` gave the wrong answer on the same task.

Raw results: [`results/benchmark_20260620_101129.json`](results/benchmark_20260620_101129.json)

---

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Ollama](https://ollama.com) — local LLM runtime

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Ollama
brew install ollama          # macOS
# or download from https://ollama.com/download
```

### Install

```bash
git clone https://github.com/josetabuyo/local-model-router
cd local-model-router
uv sync
```

### Pull local models

```bash
ollama pull qwen2.5:7b      # 4.7 GB — top model in 7/8 categories
ollama pull deepseek-r1:8b  # 5.2 GB — top model for context retrieval
```

Verify they are running:

```bash
uv run python test_connection.py
```

### Get API keys (optional — needed for cloud endpoints)

**Groq** — free tier, very fast inference:
1. Go to [console.groq.com](https://console.groq.com) → sign up
2. API Keys → Create API Key
3. Free tier includes `llama-3.3-70b-versatile` and `llama-3.1-8b-instant`

**OpenRouter** — access to many open-source models:
1. Go to [openrouter.ai](https://openrouter.ai) → sign up
2. Keys → Create Key
3. Free models are available with a `:free` suffix (rate-limited)

**Important:** OpenRouter free models share a daily quota across all users. Run benchmarks sparingly to avoid hitting limits. See [benchmark policy](#benchmark-policy) below.

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
# then edit .env:
# GROQ_API_KEY=gsk_...
# OPENROUTER_API_KEY=sk-or-...
```

### Start the router

```bash
uv run router
# Listening on http://0.0.0.0:11435
```

---

## Endpoints

### `POST /local/v1/chat/completions`

Routes only to local Ollama models. Returns a hard 400 if you specify a cloud model.

```bash
# Best local model for coding
curl http://localhost:11435/local/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "best:coding", "messages": [{"role": "user", "content": "Write a sieve of Eratosthenes."}]}'

# Explicit local model
curl http://localhost:11435/local/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "ollama/deepseek-r1:8b", "messages": [{"role": "user", "content": "Summarize this: ..."}]}'
```

### `POST /cloud/v1/chat/completions`

Routes only to cloud models (Groq, OpenRouter). Returns a hard 400 if you specify an Ollama model.

```bash
# Best cloud model for math
curl http://localhost:11435/cloud/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "best:math", "messages": [{"role": "user", "content": "Integrate x^2 from 0 to 3."}]}'

# Explicit cloud model
curl http://localhost:11435/cloud/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "groq/llama-3.3-70b-versatile", "messages": [{"role": "user", "content": "Hello"}]}'
```

### `POST /v1/chat/completions` — Hybrid

Tries the primary tier first; falls back to the other on failure. Fallback only activates for `best:<category>` — explicit `provider/model` requests are routed directly.

Default strategy: **local-first** (Ollama → cloud on failure).

```bash
# local-first (default) — try Ollama, fall back to Groq if Ollama is down
curl http://localhost:11435/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "best:coding", "messages": [{"role": "user", "content": "..."}]}'

# cloud-first — try Groq, fall back to Ollama if the API is down or quota is exhausted
curl http://localhost:11435/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Router-Strategy: cloud-first" \
  -d '{"model": "best:coding", "messages": [{"role": "user", "content": "..."}]}'
```

The response always includes an `x_router` field with routing metadata:

```json
{
  "model": "ollama/qwen2.5:7b",
  "choices": [...],
  "x_router": {
    "endpoint": "hybrid",
    "requested": "best:coding",
    "resolved": "ollama/qwen2.5:7b",
    "strategy": "local-first",
    "fallback_used": false
  }
}
```

If a fallback was triggered:

```json
{
  "x_router": {
    "fallback_used": true,
    "primary_attempted": "ollama/qwen2.5:7b",
    "primary_error": "httpx.ConnectError: ...",
    "resolved": "groq/llama-3.3-70b-versatile"
  }
}
```

### Utility endpoints

```bash
GET /health                        # liveness check + available categories
GET /v1/models                     # list all routable model identifiers
GET /v1/router/rankings/{category} # full ranked list for a category
```

---

## Model name formats

| Format | Example | Meaning |
|--------|---------|---------|
| `best:<category>` | `best:coding` | Top-ranked model for that category |
| `ollama/<model>` | `ollama/qwen2.5:7b` | Explicit local model |
| `groq/<model>` | `groq/llama-3.3-70b-versatile` | Explicit Groq model |
| `openrouter/<model>` | `openrouter/google/gemma-4-31b-it:free` | Explicit OpenRouter model |

Available categories: `reasoning`, `coding`, `math`, `summarization`, `instruction`, `multilingual`, `code_debug`, `context`

---

## Rankings

Rankings are plain YAML files — no magic, no database.

- `rankings/local.yaml` — populated from your own benchmark runs (`results/`)
- `rankings/cloud.yaml` — populated from published external benchmarks (MMLU, HumanEval, MATH-500, etc.)

**Slot 0 is the winner.** When you send `best:coding`, the router uses slot 0 of the `coding` category in `local.yaml` (or `cloud.yaml` if no local entry exists).

### Updating a ranking

Suppose you pull a new model and want to see if it deserves the top slot:

```bash
# Pull and benchmark it
ollama pull phi4:14b
uv run run_benchmark.py --models phi4:14b --task coding

# Review results/benchmark_<timestamp>.json
# If phi4:14b wins, move it to slot 0 in rankings/local.yaml
# Remove models that are no longer top from Ollama to free disk space
ollama rm <old-model>
```

---

## Running the benchmark harness

```bash
uv run run_benchmark.py                    # all local Ollama models, all 8 tasks
uv run run_benchmark.py --provider all     # local + Groq
uv run run_benchmark.py --provider groq    # Groq only
uv run run_benchmark.py --task coding      # single task
uv run run_benchmark.py --models qwen2.5:7b,deepseek-r1:8b  # specific models
uv run run_benchmark.py --throttle         # low-impact mode (slower, saves battery)
```

Results are saved to `results/benchmark_<timestamp>.json`.

### Benchmark policy

Cloud providers (Groq, OpenRouter) have rate limits and daily quotas on their free tiers. **Do not run the full benchmark suite against cloud providers repeatedly.** The intended workflow:

1. Run cloud benchmarks **once** when evaluating a new model
2. Record results in `results/` and update `rankings/cloud.yaml`
3. For subsequent comparisons, use the documented scores — not live calls

For cloud providers with published benchmarks (MMLU, HumanEval, MATH-500), use those scores directly in `cloud.yaml` and cite the source. No live calls needed.

---

## Using with any OpenAI-compatible client

Because the router speaks the OpenAI API, you can point any existing client at it:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11435/local/v1",
    api_key="not-needed",   # router runs locally, no auth required
)

response = client.chat.completions.create(
    model="best:coding",
    messages=[{"role": "user", "content": "Write a binary search in Python."}],
)
print(response.choices[0].message.content)
```

```python
# LangChain
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://localhost:11435/local/v1",
    api_key="not-needed",
    model="best:coding",
)
```

---

## Roadmap

See [`plans/nvidia-nim.md`](plans/nvidia-nim.md) for the detailed plan on adding Nvidia NIM as a provider (Llama 405B, Phi-3 128k, Nemotron).

Near-term:
- [ ] Streaming support (`stream: true`)
- [ ] Nvidia NIM provider
- [ ] `context_long` benchmark category (50k–100k token tasks)
- [ ] `best:fast` meta-category — always routes to the fastest available model regardless of quality tier

---

## License

MIT
