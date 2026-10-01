#!/usr/bin/env python3
"""Render models.md (human-readable inventory) from rankings/*.yaml — the source of truth.

Usage:  uv run scripts/render_models.py            # rewrite models.md
        uv run scripts/render_models.py --check    # exit 1 if models.md is stale

Run after every ranking change (model-scout does). README's model section
points here instead of duplicating the tables.
"""
from __future__ import annotations

import sys
from collections import OrderedDict
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "models.md"


def load(name: str) -> dict:
    return (yaml.safe_load((ROOT / "rankings" / name).read_text()) or {}).get("categories", {})


def cloud_table(cloud: dict) -> tuple[str, str]:
    """(slot-0 per category table, per-model table) for free cloud entries."""
    slot0 = ["| Categoría | Slot 0 | Resto del cascade (en orden) |", "|---|---|---|"]
    models: "OrderedDict[str, dict]" = OrderedDict()
    for cat, entries in cloud.items():
        free = [e for e in entries if not e.get("paid")]
        if not free:
            continue
        key = lambda e: f"{e.get('provider', 'groq')}/{e['model']}"
        slot0.append(f"| `{cat}` | `{key(free[0])}` | " + ", ".join(f"`{key(e)}`" for e in free[1:]) + " |")
        for i, e in enumerate(free):
            m = models.setdefault(key(e), {"provider": e.get("provider", "groq"), "ctx": e.get("context_window"),
                                            "elo": e.get("arena_elo"), "cats": []})
            m["cats"].append(f"{cat}#{i}")
            m["ctx"] = m["ctx"] or e.get("context_window")
            m["elo"] = m["elo"] or e.get("arena_elo")
    per_model = ["| Modelo | Proveedor | Categorías (categoría#slot) | Contexto | Arena ELO |", "|---|---|---|---|---|"]
    for key, m in sorted(models.items(), key=lambda kv: (kv[1]["provider"], kv[0])):
        ctx = f"{m['ctx']:,}" if isinstance(m["ctx"], int) else (m["ctx"] or "—")
        per_model.append(f"| `{key}` | {m['provider']} | {', '.join(m['cats'])} | {ctx} | {m['elo'] or '—'} |")
    return "\n".join(slot0), "\n".join(per_model)


def paid_table(cloud: dict) -> str:
    rows = ["| Modelo | Proveedor | Categorías | $/Mtok in | $/Mtok out |", "|---|---|---|---|---|"]
    seen: "OrderedDict[str, dict]" = OrderedDict()
    for cat, entries in cloud.items():
        for e in entries:
            if e.get("paid"):
                k = f"{e.get('provider', 'groq')}/{e['model']}"
                seen.setdefault(k, {**e, "cats": []})["cats"].append(cat)
    for k, e in seen.items():
        rows.append(f"| `{k}` | {e.get('provider', 'groq')} | {', '.join(e['cats'])} | {e.get('cost_per_mtok_in', '?')} | {e.get('cost_per_mtok_out', '?')} |")
    return "\n".join(rows) if seen else "_(ninguno)_"


def local_table(local: dict) -> str:
    rows = ["| Modelo | Categorías donde gana (slot 0) | tok/s (medido) | Nota |", "|---|---|---|---|"]
    models: "OrderedDict[str, dict]" = OrderedDict()
    for cat, entries in local.items():
        for i, e in enumerate(entries):
            m = models.setdefault(e["model"], {"wins": [], "tps": [], "note": ""})
            if i == 0:
                m["wins"].append(cat)
            if e.get("tokens_per_sec"):
                m["tps"].append(e["tokens_per_sec"])
            if "Removed" in str(e.get("note", "")) or "eliminado" in str(e.get("note", "")).lower():
                m["note"] = "eliminado de Ollama"
    for name, m in models.items():
        tps = f"{sum(m['tps']) / len(m['tps']):.1f}" if m["tps"] else "—"
        rows.append(f"| `{name}` | {', '.join(m['wins']) or '—'} | {tps} | {m['note']} |")
    return "\n".join(rows)


def render() -> str:
    cloud, local = load("cloud.yaml"), load("local.yaml")
    slot0, per_model = cloud_table(cloud)
    return f"""# Inventario de modelos — cloud + local

<!-- GENERADO por scripts/render_models.py desde rankings/*.yaml — no editar a mano.
     Regenerar: uv run scripts/render_models.py -->

Actualizado: {date.today().isoformat()} · Máquina: Apple Silicon, 16 GB RAM.
Fuente de verdad: `rankings/cloud.yaml` (cloud, con el log diario de auditorías
de `/model-scout` en sus `NOTE`) y `rankings/local.yaml` (benchmarks propios de Ollama).

## 1. Cascade cloud por categoría (gratis, vía el router)

Orden de proveedores por defecto en `best:<categoría>`: el que lista cada fila.
`fastest:` reordena por velocidad medida (Groq primero), `cheapest:` agrega los
pagos al final.

{slot0}

## 2. Modelos cloud gratis — dónde rankean

{per_model}

## 3. Modelos cloud pagos (sólo vía `cheapest:<categoría>`)

{paid_table(cloud)}

## 4. Modelos locales (Ollama)

Benchmark propio — ver fecha y archivo de resultados en la cabecera de
`rankings/local.yaml`. `qwen3.5:9b` (daily driver desde 2026-08-12) todavía no
está rankeado ahí: pendiente de un run del harness.

{local_table(local)}

## 5. Modelos de decisión (Jev-style, `POST /v1/systemone`)

| Backend | Modelo | Estado |
|---|---|---|
| `ollama` (local, Ollama ≥ 0.35) | `tev1:4b-q4_K_M` (2.7 GB, Together AI) — `nimble` (9B, 9.5 GB, Bespoke Labs) opcional | instalado, primero en el cascade |
| `typesafe` (Jev real) | `jev-latest` (= jev-1.13) | necesita `TYPESAFE_API_KEY` |
| `openrouter` | `jev-1.13` vía `/api/v1/systemone` | pago, necesita créditos |
| emulación | `best:instruction` forzado a JSON | último recurso, `x_router.emulated: true` |
"""


def main() -> None:
    text = render()
    if "--check" in sys.argv:
        current = OUT.read_text() if OUT.exists() else ""
        # ignore the date line when comparing
        strip = lambda t: "\n".join(l for l in t.splitlines() if not l.startswith("Actualizado:"))
        if strip(current) != strip(text):
            print("models.md is stale — run: uv run scripts/render_models.py")
            sys.exit(1)
        print("models.md up to date")
        return
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
