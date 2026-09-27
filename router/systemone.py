"""System One decision endpoint — TypeSafe's Jev, with a chat-model emulation fallback.

Jev (TypeSafe AI, launched 2026-09-15) is not a chat model: it takes a `state`
(context blob) plus typed `questions` and returns calibrated structured answers
(choice / score / noul). Request and response shapes follow TypeSafe's public
docs (docs.typesafe.ai/introduction/quickstart) so a client written against
this endpoint can be pointed at api.typesafe.ai unchanged.

Request body::

    {
      "state": "Hi, my invoice was charged twice...",
      "model": "jev-latest",                       # optional
      "questions": {
        "department": {"type": "choice", "instructions": "...",
                        "criteria": {"billing": "...", "technical": "..."}},
        "frustration": {"type": "score",  "instructions": "...",
                        "criteria": ["Calm", "Frustrated", "Angry"]},
        "is_urgent":   {"type": "noul",   "instructions": "..."}
      }
    }

Real providers (tried in this order, each only if its key is set):
  1. ``typesafe``   — direct, ``TYPESAFE_API_KEY``, POST api.typesafe.ai/v1/systemone
  2. ``openrouter`` — ``OPENROUTER_API_KEY``, POST openrouter.ai/api/v1/systemone
                       (paid: needs OpenRouter credits — the :free tier does not cover Jev)

Emulation (``X-Router-Strategy: emulate`` or when no Jev provider answers and
``JEV_EMULATE_FALLBACK`` is not "false"): the same questions are answered by
the ordinary chat cascade (``best:instruction``) forced into JSON, and mapped
back into the Jev answer shape. Answers are tagged ``x_router.emulated: true``
— probabilities come from an LLM, not from a calibrated System One model.
"""
import json
import os
import re

import httpx

TYPESAFE_BASE = "https://api.typesafe.ai/v1"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# Default model per provider. OpenRouter's /systemone rejects the namespaced
# 'typesafe/jev-latest' / 'typesafe/jev-router' ids ("Model ... does not exist",
# verified live 2026-09-27) but accepts the bare 'jev-1.13'.
DEFAULT_MODELS: dict[str, str] = {
    "typesafe": "jev-latest",
    "openrouter": "jev-1.13",
}

VALID_TYPES = ("noul", "boolean", "choice", "score")


# ── Validation ────────────────────────────────────────────────────────────────


def validate(body: dict) -> tuple[str, dict]:
    """Return (state, questions) or raise ValueError with a client-facing message."""
    state = body.get("state")
    if not isinstance(state, str) or not state.strip():
        raise ValueError("'state' must be a non-empty string")
    questions = body.get("questions")
    if not isinstance(questions, dict) or not questions:
        raise ValueError("'questions' must be a non-empty object keyed by question name")
    for name, q in questions.items():
        if not isinstance(q, dict):
            raise ValueError(f"question '{name}' must be an object")
        qtype = q.get("type")
        if qtype not in VALID_TYPES:
            raise ValueError(f"question '{name}': type must be one of {', '.join(VALID_TYPES)}")
        if not isinstance(q.get("instructions"), str) or not q["instructions"].strip():
            raise ValueError(f"question '{name}': 'instructions' must be a non-empty string")
        criteria = q.get("criteria")
        if qtype == "choice" and (not isinstance(criteria, dict) or len(criteria) < 2):
            raise ValueError(f"question '{name}': choice needs 'criteria' object with >= 2 options")
        if qtype == "score" and (not isinstance(criteria, list) or len(criteria) < 2):
            raise ValueError(f"question '{name}': score needs 'criteria' list with >= 2 levels")
    return state, questions


# ── Real providers ────────────────────────────────────────────────────────────


def provider_chain() -> list[tuple[str, str]]:
    """(provider, model) pairs for every Jev provider that has a key configured."""
    chain: list[tuple[str, str]] = []
    if os.getenv("TYPESAFE_API_KEY"):
        chain.append(("typesafe", DEFAULT_MODELS["typesafe"]))
    if os.getenv("OPENROUTER_API_KEY"):
        chain.append(("openrouter", DEFAULT_MODELS["openrouter"]))
    return chain


async def call_jev(provider: str, model: str, state: str, questions: dict, timeout: float = 30.0) -> dict:
    """POST one System One request to a real provider; raises on HTTP/network error."""
    if provider == "typesafe":
        base, key = TYPESAFE_BASE, os.getenv("TYPESAFE_API_KEY", "")
    elif provider == "openrouter":
        base, key = OPENROUTER_BASE, os.getenv("OPENROUTER_API_KEY", "")
    else:
        raise ValueError(f"Unknown System One provider '{provider}'")
    if not key:
        raise ValueError(f"{provider.upper()}_API_KEY is not set")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{base}/systemone",
            json={"model": model, "state": state, "questions": questions},
            headers={"Authorization": f"Bearer {key}", "User-Agent": "local-model-router/1.0"},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()


# ── Emulation via a chat model ────────────────────────────────────────────────


def build_emulation_messages(state: str, questions: dict) -> list[dict]:
    """Chat messages that make an ordinary LLM answer the questions as strict JSON."""
    lines = []
    for name, q in questions.items():
        qtype = q["type"]
        if qtype in ("noul", "boolean"):
            lines.append(f'- "{name}" ({qtype}): {q["instructions"]} -> answer with a probability 0..1 that this is true')
        elif qtype == "choice":
            opts = "; ".join(f'"{k}": {v}' for k, v in q["criteria"].items())
            lines.append(
                f'- "{name}" (choice): {q["instructions"]}. Options: {opts} '
                f'-> answer with {{"choice": <option key>, "confidence": 0..1}}'
            )
        else:  # score
            levels = "; ".join(f"{i}: {c}" for i, c in enumerate(q["criteria"]))
            lines.append(
                f'- "{name}" (score): {q["instructions"]}. Levels: {levels} '
                f'-> answer with {{"score": <level index>, "confidence": 0..1}}'
            )
    system = (
        "You are a decision engine. Read STATE, then answer every QUESTION. "
        "Do not explain. Reply with ONLY one JSON object whose keys are exactly the "
        "question names and whose values follow each question's answer format."
    )
    user = "STATE:\n" + state + "\n\nQUESTIONS:\n" + "\n".join(lines) + "\n\nJSON:"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _clamp(x, default: float = 0.5) -> float:
    try:
        return min(1.0, max(0.0, float(x)))
    except (TypeError, ValueError):
        return default


def parse_emulation(content: str, questions: dict) -> dict:
    """Map the chat model's JSON into Jev-shaped answers. Raises ValueError if unusable."""
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("emulation: no JSON object in model output")
    try:
        raw = json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"emulation: invalid JSON from model ({e})")
    if not isinstance(raw, dict):
        raise ValueError("emulation: model output is not a JSON object")

    answers: dict = {}
    for name, q in questions.items():
        if name not in raw:
            raise ValueError(f"emulation: model omitted question '{name}'")
        val = raw[name]
        qtype = q["type"]
        if qtype in ("noul", "boolean"):
            if isinstance(val, dict):
                val = val.get("probability", val.get("value", val.get("noul")))
            if isinstance(val, bool):
                val = 1.0 if val else 0.0
            answers[name] = {"type": qtype, "noul": _clamp(val)}
        elif qtype == "choice":
            choice = val.get("choice") if isinstance(val, dict) else val
            keys = list(q["criteria"].keys())
            if choice not in keys:
                raise ValueError(f"emulation: '{name}' choice {choice!r} not in {keys}")
            conf = _clamp(val.get("confidence"), 0.5) if isinstance(val, dict) else 0.5
            others = (1.0 - conf) / max(1, len(keys) - 1)
            answers[name] = {
                "type": "choice",
                "choice": choice,
                "confidence": conf,
                "probabilities": {k: (conf if k == choice else others) for k in keys},
            }
        else:  # score
            idx = val.get("score") if isinstance(val, dict) else val
            try:
                idx = int(idx)
            except (TypeError, ValueError):
                raise ValueError(f"emulation: '{name}' score {idx!r} is not an integer level")
            levels = q["criteria"]
            if not 0 <= idx < len(levels):
                raise ValueError(f"emulation: '{name}' score {idx} outside 0..{len(levels) - 1}")
            conf = _clamp(val.get("confidence"), 0.5) if isinstance(val, dict) else 0.5
            answers[name] = {
                "type": "score",
                "score": float(idx),
                "confidence": conf,
                "legend": {str(i): lvl for i, lvl in enumerate(levels)},
            }
    return answers
