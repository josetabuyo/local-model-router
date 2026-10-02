#!/usr/bin/env python3
"""Compare System One backends on the same body: local Ollama (tev1/nimble),
TypeSafe Jev (direct), OpenRouter Jev, and the router's chat-model emulation.

Usage:
  uv run scripts/jev_compare.py                       # plans/jev-example.json
  uv run scripts/jev_compare.py path/to/body.json
  uv run scripts/jev_compare.py --models tev1:4b-q4_K_M,nimble   # local models to try

Needs the router running for the 'emulate' column (uv run router, port 9002);
each other column runs only if its backend is reachable / its key is set.
Prints, per question: the answer each backend gave, its confidence, and the
latency, so calibration differences between real Jev and the local models
are visible side by side.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

OLLAMA = "http://localhost:11434/v1/systemone"
TYPESAFE = "https://api.typesafe.ai/v1/systemone"
OPENROUTER = "https://openrouter.ai/api/v1/systemone"
ROUTER = os.getenv("ROUTER_URL", "http://localhost:9002") + "/v1/systemone"


def call(url: str, body: dict, headers: dict | None = None, runs: int = 2) -> tuple[dict | None, float, str]:
    """Return (answers, best_latency_s, error). Two runs: the first warms the model."""
    best, last_err, answers = float("inf"), "", None
    for _ in range(runs):
        t0 = time.perf_counter()
        try:
            r = httpx.post(url, json=body, headers=headers or {}, timeout=180)
            dt = time.perf_counter() - t0
            if r.status_code != 200:
                last_err = f"HTTP {r.status_code} {r.text[:120]}"
                continue
            answers = r.json().get("answers")
            best = min(best, dt)
        except Exception as e:
            last_err = str(e)[:120]
    return answers, best, last_err if answers is None else ""


def summarize(ans: dict) -> str:
    t = ans.get("type")
    if t in ("noul", "boolean"):
        return f"{ans.get('noul', 0):.2f}"
    if t == "choice":
        return f"{ans.get('choice')} ({ans.get('confidence', 0):.2f})"
    if t == "score":
        return f"{ans.get('score', 0):.2f} ({ans.get('confidence', 0):.2f})"
    return json.dumps(ans)[:30]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("body", nargs="?", default=str(ROOT / "plans" / "jev-example.json"))
    ap.add_argument("--models", default=os.getenv("JEV_LOCAL_MODEL", "tev1:4b-q4_K_M"),
                    help="comma-separated local Ollama decision models")
    args = ap.parse_args()
    base = json.loads(Path(args.body).read_text())
    base.pop("model", None)

    columns: list[tuple[str, dict | None, float, str]] = []
    for m in [x.strip() for x in args.models.split(",") if x.strip()]:
        columns.append((f"ollama/{m}", *call(OLLAMA, {**base, "model": m})))
    if os.getenv("TYPESAFE_API_KEY"):
        columns.append(("typesafe/jev-latest", *call(
            TYPESAFE, {**base, "model": "jev-latest"},
            {"Authorization": f"Bearer {os.environ['TYPESAFE_API_KEY']}"})))
    else:
        columns.append(("typesafe/jev-latest", None, 0.0, "TYPESAFE_API_KEY not set"))
    if os.getenv("OPENROUTER_API_KEY"):
        columns.append(("openrouter/jev-1.13", *call(
            OPENROUTER, {**base, "model": "jev-1.13"},
            {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"}, runs=1)))
    columns.append(("router/emulate", *call(ROUTER, base, {"X-Router-Strategy": "emulate"}, runs=1)))

    names = [c[0] for c in columns]
    w = max(len(n) for n in names) + 2
    print(f"{'question':<14}" + "".join(f"{n:<{w}}" for n in names))
    for q in base["questions"]:
        row = f"{q:<14}"
        for _, answers, _, err in columns:
            row += f"{(summarize(answers[q]) if answers and q in answers else '—'):<{w}}"
        print(row)
    print(f"{'latency (s)':<14}" + "".join(f"{(f'{lat:.2f}' if answers else '—'):<{w}}" for _, answers, lat, _ in columns))
    errs = [(n, e) for n, _, _, e in columns if e]
    if errs:
        print("\nunavailable:")
        for n, e in errs:
            print(f"  {n}: {e}")
    sys.exit(0)


if __name__ == "__main__":
    main()
