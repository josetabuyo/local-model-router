"""OpenAI-compatible HTTP router for local and cloud models.

Endpoints
---------
POST /local/v1/chat/completions   — Local (Ollama) only; cascades through all ranked local models.
                                    Hard 400 if the model string resolves to a cloud provider.
POST /cloud/v1/chat/completions   — Cloud only (NVIDIA NIM → Groq → OpenRouter cascade).
                                    Hard 400 if the model string resolves to a local provider.
POST /v1/chat/completions         — Hybrid full cascade; strategy via X-Router-Strategy header.
                                    'local-first' (default): all local, then all cloud
                                    'cloud-first':           all cloud, then all local

GET  /v1/models                   — list all routable model identifiers
GET  /v1/router/rankings/{cat}    — full ranked list for a category
GET  /health                      — liveness check

'stream: true' is accepted on all three chat/completions endpoints, but is
never forwarded to a provider — the cascade needs the full response before
it can decide success/failure. The complete response is instead replayed as
a fake SSE stream (see _fake_stream) so streaming-only clients (e.g. the
Claude Code harness) still get a well-formed stream, just without real
token-by-token incremental delivery.

Cascade failure conditions (tries next model on any of these):
  - HTTP error (non-2xx)
  - Network / timeout exception
  - Empty content in choices[0].message.content with no tool_calls either
    (e.g. content moderation, silent rate-limit). A tool_calls-only response
    (content=null, finish_reason=tool_calls) is NOT treated as empty.
  - Content that is only a <think>...</think> block (reasoning model, all tokens consumed by
    the thought trace before the actual answer — treated as empty after stripping)
"""
from dotenv import load_dotenv

load_dotenv()

import json
import re
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from router.cache import CACHE_ENABLED, ResponseCache, make_key
from router.dispatcher import Dispatcher
from router.registry import Registry

app = FastAPI(title="local-model-router", version="1.0.0")
registry = Registry()
dispatcher = Dispatcher()
cache = ResponseCache()

# Per-provider timeouts used when the chain has more than one entry.
# Shorter than the standalone defaults so the cascade can complete within
# a reasonable wall-clock budget (e.g. a client with --max-time 90).
_CASCADE_TIMEOUTS: dict[str, float] = {
    "nvidia": 45.0,
    "groq": 30.0,
    "openrouter": 45.0,
    "ollama": 180.0,
}

# ── Utility ───────────────────────────────────────────────────────────────────


def _extract_body(raw: dict) -> tuple[str, dict, bool]:
    """Return (requested_model, provider_payload, want_stream) or raise HTTPException.

    'stream' is never forwarded to a provider — the cascade needs the full
    response to decide success/failure, so providers are always called
    non-streaming internally. If the client asked for stream:true, the
    complete response is re-emitted as a fake SSE stream (see _fake_stream).
    'stream_options' is stream-only too (providers 400 on it once 'stream' is
    stripped) and is dropped for the same reason.
    """
    model = raw.get("model", "")
    if not model:
        raise HTTPException(400, "'model' field is required")
    want_stream = bool(raw.get("stream", False))
    payload = {k: v for k, v in raw.items() if k not in ("model", "stream", "stream_options")}
    return model, payload, want_stream


def _fake_stream(result: dict):
    """Re-emit an already-complete chat.completion as an OpenAI-style SSE stream.

    Used when the client requested stream:true. The whole response is known
    up front (the cascade already ran to completion), so this just wraps it
    in the chunk framing clients expect — one role chunk, one content/tool_calls
    delta, one finish_reason chunk, then [DONE].
    """
    choice = result.get("choices", [{}])[0]
    message = choice.get("message", {})
    chunk_id = result.get("id", "chatcmpl-stream")
    created = result.get("created", 0)
    model = result.get("model", "")

    def sse(delta: dict, finish_reason: str | None) -> str:
        chunk = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        return f"data: {json.dumps(chunk)}\n\n"

    yield sse({"role": "assistant"}, None)

    delta = {}
    if message.get("content"):
        delta["content"] = message["content"]
    if message.get("tool_calls"):
        delta["tool_calls"] = message["tool_calls"]
    if delta:
        yield sse(delta, None)

    yield sse({}, choice.get("finish_reason", "stop"))
    yield "data: [DONE]\n\n"


async def _dispatch(provider: str, model_id: str, payload: dict, endpoint: str, requested: str) -> JSONResponse:
    """Call one provider and return a decorated JSONResponse."""
    try:
        result = await dispatcher.call(provider, model_id, payload)
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Provider error ({provider}): {e.response.text[:400]}")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"Provider error ({provider}): {e}")

    result["model"] = f"{provider}/{model_id}"
    result["x_router"] = {
        "endpoint": endpoint,
        "requested": requested,
        "resolved": f"{provider}/{model_id}",
        "fallback_used": False,
    }
    return JSONResponse(result)


def _extract_content(result: dict) -> str:
    """Return the usable text content from the first choice, or '' if absent/empty.

    Strips complete <think>...</think> blocks emitted by reasoning models (Qwen3,
    DeepSeek, Kimi) so the cascade sees the actual answer.  If the block is
    incomplete (truncated by a low max_tokens budget before the answer arrived),
    the remaining '<think>' prefix is also treated as empty so the cascade
    falls through to the next provider.
    """
    try:
        content = result["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return ""
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    # Incomplete think block — answer never arrived (e.g. max_tokens too low).
    if "<think>" in content:
        return ""
    return content


def _has_tool_calls(result: dict) -> bool:
    """True if the first choice is a tool-call response (content is legitimately null)."""
    try:
        return bool(result["choices"][0]["message"].get("tool_calls"))
    except (KeyError, IndexError, TypeError):
        return False


async def _dispatch_chain(
    chain: list[tuple[str, str]],
    payload: dict,
    endpoint: str,
    requested: str,
    strategy: str,
    want_stream: bool = False,
) -> JSONResponse | StreamingResponse:
    """Try each (provider, model_id) in order; return on first non-empty success.

    Responses to '<best|cheapest|fastest>:<category>' requests are cached
    (bounded, TTL'd — see router.cache) since those are the calls test/benchmark
    traffic repeats verbatim. Explicit provider/model requests always dispatch live.
    """
    cache_key = None
    if CACHE_ENABLED and requested.startswith(("best:", "cheapest:", "fastest:")):
        cache_key = make_key(endpoint, strategy, requested, payload)
        cached = cache.get(cache_key)
        if cached is not None:
            hit = dict(cached)
            hit["x_router"] = {**hit["x_router"], "cached": True}
            if want_stream:
                return StreamingResponse(_fake_stream(hit), media_type="text/event-stream")
            return JSONResponse(hit)

    errors: list[str] = []
    cascade = len(chain) > 1
    for i, (provider, model_id) in enumerate(chain):
        timeout = _CASCADE_TIMEOUTS.get(provider) if cascade else None
        try:
            result = await dispatcher.call(provider, model_id, payload, timeout=timeout)
        except httpx.HTTPStatusError as e:
            errors.append(f"{provider}/{model_id}: HTTP {e.response.status_code} — {e.response.text[:200]}")
            continue
        except ValueError as e:
            errors.append(f"{provider}/{model_id}: {e}")
            continue
        except Exception as e:
            errors.append(f"{provider}/{model_id}: {e}")
            continue

        if not _extract_content(result) and not _has_tool_calls(result):
            errors.append(f"{provider}/{model_id}: empty content in response (finish_reason={result.get('choices', [{}])[0].get('finish_reason', 'unknown')})")
            continue

        result["model"] = f"{provider}/{model_id}"
        result["x_router"] = {
            "endpoint": endpoint,
            "requested": requested,
            "resolved": f"{provider}/{model_id}",
            "strategy": strategy,
            "fallback_used": i > 0,
            "cached": False,
            **({"errors": errors, "primary_attempted": f"{chain[0][0]}/{chain[0][1]}"} if i > 0 else {}),
        }
        if cache_key is not None:
            cache.set(cache_key, result)
        if want_stream:
            return StreamingResponse(_fake_stream(result), media_type="text/event-stream")
        return JSONResponse(result)

    raise HTTPException(502, {"message": "All providers in the chain failed", "errors": errors})


# ── Routes ────────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "categories": registry.categories()}


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [{"id": m, "object": "model", "owned_by": "router"} for m in registry.list_models()],
    }


@app.get("/v1/router/cache")
async def cache_stats():
    return cache.stats()


@app.get("/v1/router/rankings/{category}")
async def category_rankings(category: str):
    entries = registry.describe(category)
    if not entries:
        raise HTTPException(404, f"No rankings found for category '{category}'")
    return {"category": category, "rankings": entries}


@app.post("/local/v1/chat/completions")
async def chat_local(request: Request):
    """Cascade through all ranked local (Ollama) models in order.
    Hard 400 if the model string resolves to a cloud provider.
    """
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")

    requested, payload, want_stream = _extract_body(raw)

    try:
        chain = registry.resolve_local_chain(requested)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return await _dispatch_chain(chain, payload, endpoint="local", requested=requested, strategy="local-only", want_stream=want_stream)


@app.post("/cloud/v1/chat/completions")
async def chat_cloud(request: Request):
    """Cascade through all ranked cloud models in order (NVIDIA NIM → Groq → OpenRouter).
    Hard 400 if the model string resolves to a local (Ollama) provider.
    """
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")

    requested, payload, want_stream = _extract_body(raw)

    try:
        chain = registry.resolve_cloud_chain(requested)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return await _dispatch_chain(chain, payload, endpoint="cloud", requested=requested, strategy="cloud-only", want_stream=want_stream)


@app.post("/v1/chat/completions")
async def chat_hybrid(request: Request):
    """Hybrid endpoint — tries the primary tier, falls back to the other on failure.

    X-Router-Strategy header:
      local-first  (default) — try Ollama, fall back to cloud
      cloud-first             — try cloud, fall back to Ollama

    Fallback only activates for best:<category> requests.
    Explicit provider/model requests (e.g. ollama/qwen2.5:7b) are routed directly.
    """
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")

    requested, payload, want_stream = _extract_body(raw)
    strategy = request.headers.get("x-router-strategy", "local-first").lower()
    if strategy not in ("local-first", "cloud-first"):
        raise HTTPException(400, "X-Router-Strategy must be 'local-first' or 'cloud-first'")

    try:
        chain = registry.resolve_chain(requested, strategy=strategy)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return await _dispatch_chain(chain, payload, endpoint="hybrid", requested=requested, strategy=strategy, want_stream=want_stream)
