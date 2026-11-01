#!/usr/bin/env python3
"""Route a dictated phrase to the right LAS agent with the router's /v1/systemone.

Reference client for LocalAgentSociety's POST /route (backend :8700): the
candidates are the agents' scope ladder (long_description, else
short_description, from each .las-agent.json); one `choice` question picks
the agent and one `noul` says how clearly it belongs to one agent.

Usage:
  uv run scripts/las_route.py "mandale un whatsapp a Diego"   # one phrase → JSON
  uv run scripts/las_route.py --cases                          # built-in labelled phrases

Request (POST {ROUTER_URL}/v1/systemone, no model → local d3:4b-nvfp4):
  {"state": "<text>",
   "questions": {"agent":     {"type": "choice", "instructions": "...",
                               "criteria": {"<AgentName>": "<scope>", ...}},
                 "confident": {"type": "noul", "instructions": "..."}}}
Response (relevant part):
  {"answers": {"agent": {"type": "choice", "choice": "Wavi", "confidence": 0.82,
                         "probabilities": {"Wavi": 0.82, ...}},
               "confident": {"type": "noul", "noul": 0.80}},
   "x_router": {"resolved": "ollama/d3:4b-nvfp4", "local": true, "fallback_used": false, ...}}
Decide on answers.agent.confidence (top probability) and its margin over the
runner-up; the `confident` noul runs low (0.53-0.80 on correct picks).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROUTER = os.getenv("ROUTER_URL", "http://localhost:9002") + "/v1/systemone"

CASES = [
    ("la mac está lentísima, fijate qué proceso se come la memoria", "System"),
    ("mandale un whatsapp a Diego diciendo que llego tarde", "Wavi"),
    ("emití la factura de octubre para el cliente en ARCA", "TechVentas"),
    ("qué modelo local conviene para clasificar tickets", "LocalModels"),
    ("el widget no muestra la burbuja del micrófono", "LocalAgentSociety"),
    ("entrená de nuevo la política del humanoide para caminar", "RuGIAR"),
    ("cómo vienen las cargas de Glue de SAP en el data lake", "DataLake"),
    ("revisá el PR que abrió Javier en relay-agents", "relay-reviewer"),
    ("cuánto me pagaron en Payoneer este mes", "billing"),
    ("la app de mi mamá no está transcribiendo", "AppBlanca"),
    ("el relay entre las dos macs no entrega mensajes", "Vortexia"),
    ("armá el cuestionario de jugadores del club de rugby", "AppDelSur"),
]


def candidates() -> dict[str, str]:
    """Agent name → scope text, for every registered agent that has one."""
    out = subprocess.run(["las", "agents"], capture_output=True, text=True, check=True).stdout
    crit: dict[str, str] = {}
    for line in out.splitlines():
        cfg = Path(line.split()[-1]) / ".las-agent.json" if line.strip() else None
        if cfg and cfg.exists():
            j = json.loads(cfg.read_text())
            scope = j.get("long_description") or j.get("short_description")
            if scope:
                crit[j["name"]] = scope
    return crit


def route(text: str, crit: dict[str, str]) -> dict:
    body = {"state": text, "questions": {
        "agent": {"type": "choice", "instructions": "Which agent should handle this spoken request",
                  "criteria": crit},
        "confident": {"type": "noul", "instructions": "The request clearly belongs to one agent"}}}
    r = httpx.post(ROUTER, json=body, timeout=60)
    r.raise_for_status()
    return r.json()


def main() -> None:
    crit = candidates()
    if sys.argv[1:] and sys.argv[1] != "--cases":
        print(json.dumps(route(" ".join(sys.argv[1:]), crit), ensure_ascii=False, indent=2))
        return
    hits, lats = 0, []
    for text, expected in CASES:
        t0 = time.perf_counter()
        res = route(text, crit)
        lats.append(time.perf_counter() - t0)
        a = res["answers"]["agent"]
        ok = a["choice"] == expected
        hits += ok
        print(f"{'✓' if ok else '✗'} {a['choice']:<18} {a.get('confidence', 0):.2f} "
              f"conf={res['answers']['confident']['noul']:.2f} {lats[-1]:.1f}s  [{expected}] {text}")
    print(f"\n{len(crit)} candidates · {hits}/{len(CASES)} · p50 {sorted(lats)[len(lats) // 2]:.1f}s "
          f"· {res.get('x_router', {}).get('resolved')}")


if __name__ == "__main__":
    main()
