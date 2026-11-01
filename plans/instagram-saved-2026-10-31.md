# Guardados de Instagram (@jozbuyo) — inventario 2026-10-31

205 posts guardados (colección "All posts"; "Va" vacía). ~100 son de tech/IA,
casi todos 2026. Lo que sigue son afirmaciones de los posts, sin verificar
salvo donde dice "probado". Se avanza de a uno.

## Para LocalModels, en orden de prueba

| # | Qué | Estado |
|---|---|---|
| 1 | **Laya** — github.com/NandhaKishorM/laya, Apache-2.0, 421M, `laya-serve` expone `POST /v1/systemone` (compatible Jev) | **Probado 2026-10-31**, ver abajo |
| 2 | **ScaleDown CDMs** (13-10-2026): classify / extract / summarize, `langchain-scaledown` | pendiente |
| 3 | **Unlimited OCR** (Baidu, 3B, MIT): PDFs de 100 páginas en una pasada, local | pendiente |
| 4 | **AirLLM** / **Strata** (offload capa a capa / RAM+GPU+SSD; Strata soporta DeepSeek-V4.1-Flash-1017) | pendiente |
| 5 | Jev + RAG: usar `/v1/systemone` como gate de pasajes antes del LLM | idea |
| 6 | OpenRouter **Fusion** (varios modelos en paralelo sobre un prompt) | idea para el router |
| 7 | Ollama habla API de Anthropic → Claude Code contra modelos locales | pendiente |

Harness de benchmark: "AI judges are unreliable" (Stanford), Harness Zero
(Google + Peking), cordis harness (DeepSeek), Cloudflare code-mode vs MCP.
Voz: Dessa (Block, corre en MacBook Pro), PersonaPlex-7B (NVIDIA), Fish Audio.
Robótica (→ Robotics / kit edge): Arduino VENTUNO Q, LeRobot, π0, MuJoCo,
PhoneBot, SimReady, MotionBricks, SolidCraft MCP, Unreal MCP.

## Laya — prueba 2026-10-31

- `uv pip install "laya[serve]"` (laya 0.4.19, torch 2.15, MPS ok) en venv
  aislado; `LAYA_HOST=127.0.0.1 LAYA_PORT=<puerto LAS> LAYA_DEVICE=mps LAYA_PRELOAD=1 laya-serve`.
- `plans/jev-example.json` sin cambios → respuesta con la forma de Jev
  (`answers.<q>.choice|score|noul` + `probabilities` + `confidence` + `usage`).
  ~77 ms en caliente (inglés).
- Calidad zero-shot, mezclada:
  - EN: department=billing (0.48) ✗ (era technical), frustration=civil ✓, urgent 0.76 ✓.
  - ES (enruta a `multilingual`): área=técnico (0.59) ✓, enojo=muy enojado ~ exagerado,
    urgente 0.18 ✗.
- El README dice que el fine-tune en el dominio sube de 0.36 a 0.77 (script MPS incluido).

### Integrado al router (2026-10-31)

- `router/systemone.py`: proveedor `laya`, primero del cascade
  (`laya,ollama,typesafe,openrouter`), activo sólo si `LAYA_URL` está seteado
  (opcional `LAYA_API_KEY`). Modelo `auto`; un id `jev*` nunca se le manda.
  `x_router.local: true`. Si Laya no responde, cae a Ollama / Jev cloud / emulación.
- `scripts/jev_compare.py`: columna `laya` + modo `--cases` (acierto por pregunta).
- `plans/systemone-cases.json`: 12 casos etiquetados a mano (6 EN, 6 ES).

Resultado `--cases` (Ollama caído, sin key de TypeSafe):

| backend | department | frustration | is_urgent | total | p50 |
|---|---|---|---|---|---|
| laya (zero-shot) | 10/12 | 6/12 | 9/12 | **69%** | **0.09 s** |
| router/emulate (LLM cloud) | 11/12 | 12/12 | 12/12 | **97%** | 0.78 s |

Lectura: Laya es ~9× más rápido, gratis y offline, pero sin fine-tune falla
mucho en `score` (frustración) y algo en urgencia. Las etiquetas las puse yo,
así que favorecen el criterio de un LLM; faltan casos reales.

### Con Ollama 0.40.13 (2026-10-31, noche)

Ollama no estaba caído: el servicio de brew nunca se rearrancó tras el upgrade
a 0.35. Ahora `brew upgrade ollama` (→ 0.40.13) + `brew services start ollama`.
La primera corrida comparó varios modelos seguidos sin descargarlos y la Mac
se congeló (reset forzado 19:52, `btn_rst force_off`). Se repitió de a un
modelo por vez con `ollama stop` entre cada uno:

| backend | department | frustration | is_urgent | total | p50 |
|---|---|---|---|---|---|
| ollama/d3:4b-nvfp4 | 11/12 | 12/12 | 12/12 | **97%** | 1.41 s |
| ollama/laya | 8/12 | 5/12 | 11/12 | 67% | 0.13 s |
| ollama/tev1 (0.8b y 4b) | — | — | — | 400: formato viejo, hay que volver a hacer pull | — |

→ `JEV_LOCAL_MODEL` por defecto pasa a `d3:4b-nvfp4` (iguala a la emulación
con LLM en la nube, local y gratis).

Idea siguiente: destilar — usar las respuestas de la emulación (o de Jev
real) como etiquetas para el fine-tune de Laya con su script MPS
(`notebooks/laya_finetune_typed_decisions_mps.py`), y volver a medir.
