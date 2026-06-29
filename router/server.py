"""OpenAI-compatible HTTP router for local and cloud models.

Endpoints
---------
POST /local/v1/chat/completions   — Ollama only; hard error if no local model
POST /cloud/v1/chat/completions   — Cloud only (Groq / OpenRouter / NVIDIA NIM); hard error if no cloud model
POST /v1/chat/completions         — Hybrid; strategy via X-Router-Strategy header
                                    'local-first' (default): try local, fall back to cloud
                                    'cloud-first':           try cloud, fall back to local

GET  /v1/models                   — list all routable model identifiers
GET  /v1/router/rankings/{cat}    — full ranked list for a category
GET  /health                      — liveness check
"""
from dotenv import load_dotenv

load_dotenv()

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from router.dispatcher import Dispatcher
from router.registry import Registry

app = FastAPI(title="local-model-router", version="1.0.0")
registry = Registry()
dispatcher = Dispatcher()

# ── Utility ───────────────────────────────────────────────────────────────────


def _extract_body(raw: dict) -> tuple[str, dict]:
    """Return (requested_model, provider_payload) or raise HTTPException."""
    model = raw.get("model", "")
    if not model:
        raise HTTPException(400, "'model' field is required")
    if raw.get("stream", False):
        raise HTTPException(400, "Streaming not yet supported by this router")
    payload = {k: v for k, v in raw.items() if k != "model"}
    return model, payload


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


async def _dispatch_chain(
    chain: list[tuple[str, str]],
    payload: dict,
    endpoint: str,
    requested: str,
    strategy: str,
) -> JSONResponse:
    """Try each (provider, model_id) in order; return on first success."""
    errors: list[str] = []
    for i, (provider, model_id) in enumerate(chain):
        try:
            result = await dispatcher.call(provider, model_id, payload)
        except httpx.HTTPStatusError as e:
            errors.append(f"{provider}/{model_id}: HTTP {e.response.status_code} — {e.response.text[:200]}")
            continue
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            errors.append(f"{provider}/{model_id}: {e}")
            continue

        result["model"] = f"{provider}/{model_id}"
        result["x_router"] = {
            "endpoint": endpoint,
            "requested": requested,
            "resolved": f"{provider}/{model_id}",
            "strategy": strategy,
            "fallback_used": i > 0,
            **({"primary_error": errors[0], "primary_attempted": f"{chain[0][0]}/{chain[0][1]}"} if i > 0 else {}),
        }
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


@app.get("/v1/router/rankings/{category}")
async def category_rankings(category: str):
    entries = registry.describe(category)
    if not entries:
        raise HTTPException(404, f"No rankings found for category '{category}'")
    return {"category": category, "rankings": entries}


@app.post("/local/v1/chat/completions")
async def chat_local(request: Request):
    """Route to the best local (Ollama) model for the requested category.
    Hard 400 if the model string resolves to a cloud provider.
    """
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")

    requested, payload = _extract_body(raw)

    try:
        provider, model_id = registry.resolve_local_only(requested)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return await _dispatch(provider, model_id, payload, endpoint="local", requested=requested)


@app.post("/cloud/v1/chat/completions")
async def chat_cloud(request: Request):
    """Route to the best cloud model for the requested category.
    Hard 400 if the model string resolves to a local (Ollama) provider.
    """
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")

    requested, payload = _extract_body(raw)

    try:
        provider, model_id = registry.resolve_cloud_only(requested)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return await _dispatch(provider, model_id, payload, endpoint="cloud", requested=requested)


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

    requested, payload = _extract_body(raw)
    strategy = request.headers.get("x-router-strategy", "local-first").lower()
    if strategy not in ("local-first", "cloud-first"):
        raise HTTPException(400, "X-Router-Strategy must be 'local-first' or 'cloud-first'")

    try:
        chain = registry.resolve_chain(requested, strategy=strategy)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return await _dispatch_chain(chain, payload, endpoint="hybrid", requested=requested, strategy=strategy)
