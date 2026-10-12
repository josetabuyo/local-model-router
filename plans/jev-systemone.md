# Jev (TypeSafe System One) en el router — estado 2026-10-01

## Qué es

Jev no es un LLM de chat: recibe un `state` (contexto) + `questions` tipadas
(`choice` / `score` / `noul`) y devuelve decisiones estructuradas con
probabilidades calibradas. 70–500 ms, $0.042/M tokens de entrada, salida
gratis. Pensado para clasificación, routing, guardrails y lógica condicional
en pipelines — no para chat ni generación de texto. Fuente primaria:
typesafe.ai/blog/introducing-system-one-models-and-jev y
docs.typesafe.ai/introduction/quickstart (verificadas 2026-09-27).

## Vías de acceso (verificado 2026-09-27)

| Vía | Estado | Qué hace falta |
|---|---|---|
| Directo `api.typesafe.ai/v1/systemone` | Consola `console.typesafe.ai/login` **viva**, login Google o email, sin banner de "signups pausados" (visto en browser). Blogs de terceros (jevmodel.org, 24-09) reportan $5/mes de crédito sin tarjeta; otros (flaviocopes, 24-09) reportaron signups pausados el 22-09. | Crear cuenta y key → `TYPESAFE_API_KEY` en `.env`. Lo tiene que hacer José (no creo cuentas). |
| OpenRouter `openrouter.ai/api/v1/systemone` | Endpoint **vivo y validando** el esquema (probe real: 400 por `questions` como array, luego 403 "Key limit exceeded"). Modelo aceptado: `jev-1.13` (los ids `typesafe/jev-latest` y `typesafe/jev-router` devuelven "does not exist" en este endpoint). | Nuestra key es free-tier con **0 créditos** (`/auth/key`: `limit: 0`, `is_free_tier: true`). Jev es pago → cargar créditos en OpenRouter. |
| Vercel AI Gateway `typesafe-ai/jev` | Listado ($0.042/M input, output 0). | Tarjeta obligatoria (`customer_verification_required`, probado 2026-09-18). Descartado. |
| NVIDIA NIM / Groq / Gemini | No lo sirven. | — |

## Lo implementado

- `router/systemone.py` — validación del request (esquema TypeSafe), cascade
  de proveedores reales (`typesafe` → `openrouter`, cada uno sólo si tiene
  key), y emulación con el cascade de chat (`best:instruction`) forzado a JSON
  y mapeado a la forma de respuesta de Jev.
- `router/server.py` — `POST /v1/systemone`. Header `X-Router-Strategy`:
  `jev` (default: proveedores reales, emulación sólo si todos fallan y
  `JEV_EMULATE_FALLBACK != false`), `emulate` (salta a la emulación —
  útil hoy, sin key), `jev-only` (nunca emula).
- La respuesta lleva `x_router.emulated` para que el cliente sepa si las
  probabilidades vienen de Jev (calibradas) o de un LLM (no calibradas).
- `tests/test_systemone.py` — validación, cascade con mocks, emulación.

## Próximos pasos

1. José crea la cuenta en console.typesafe.ai y pega `TYPESAFE_API_KEY`.
2. `uv run router` y probar:
   ```bash
   curl -s localhost:9002/v1/systemone -H 'Content-Type: application/json' -d @plans/jev-example.json | jq
   ```
3. Comparar la salida real de Jev contra la emulación con el mismo body
   (`-H 'X-Router-Strategy: emulate'`) y anotar la diferencia de calibración.
4. Si Jev rinde: exponer categorías de decisión (`classify`, `guardrail`)
   para Pulpo/Luganense, que hoy clasifican con `best:instruction`.

## Nueva vía: Ollama local (hallado por model-scout 2026-09-29)

Ollama **v0.35.0** (2026-09-28; stable en GitHub y en Homebrew desde 2026-09-30) agrega modelos de decisión en
`POST /v1/systemone`, "based on TypeSafe's Jev API": mismo esquema de
`state` + `questions` con tipos `choice` / `noul` / `score`, respuesta con
`answers.<q>.choice` + `probabilities` + `confidence` y `usage`. Fuente:
github.com/ollama/ollama/releases/tag/v0.35.0 (verificado 2026-09-29).

| Modelo | Origen | Tamaño | Notas |
|---|---|---|---|
| `tev1:4b-q4_K_M` | Together AI, 4B | 2.7 GB | 256K ctx. El que entra cómodo en 16 GB junto con qwen2.5:7b |
| `tev1:0.8b` | Together AI, 0.8B | 812 MB | Para clasificación rápida/barata |
| `nimble` | Bespoke Labs, 9B (fine-tune de Qwen3.5-9B) | 9.5 GB | Apache 2.0, "requires Ollama 0.35". 75.7% en 13 datasets públicos; choice 81.6%, score 54.6%. Justo para 16 GB |

Fuentes: ollama.com/library/tev1/tags, ollama.com/library/nimble (2026-09-29).

Sería un backend **gratis y local** para el cascade de `router/systemone.py`,
sin key ni créditos, y con probabilidades que vienen de un modelo de decisión,
no de la emulación con un LLM de chat. Todavía **no está integrado** porque:

- El cliente local es 0.21.2. Desde 2026-09-30 brew stable ya es 0.35.0
  (formulae.brew.sh), así que alcanza con `brew upgrade ollama` — falta
  que José lo corra.
- No está verificado que las probabilidades de tev1/nimble estén calibradas
  igual que las de Jev: Ollama dice "based on", no que sea el mismo modelo.

Pasos propuestos (decide José):

1. `brew upgrade ollama` (stable 0.35.0 desde 2026-09-30) y `ollama pull tev1:4b-q4_K_M`.
2. Probar `curl localhost:11434/v1/systemone -d @plans/jev-example.json`.
3. Agregar `ollama` como primer proveedor del cascade en `router/systemone.py`
   (antes de `typesafe` → `openrouter`), con el modelo configurable
   (`JEV_LOCAL_MODEL`, default `tev1`), y marcar `x_router.provider` en la
   respuesta para distinguir local de Jev real.
4. Comparar local, emulación y (si aparece la key) Jev real con el mismo body.

## 2026-10-01 — INTEGRADO el backend local

- `brew upgrade ollama` hecho (0.21.2 → 0.35.0), `ollama pull tev1:4b-q4_K_M`
  (2.7 GB). Probe directo a `localhost:11434/v1/systemone` con
  `plans/jev-example.json`: `technical` 0.96, `is_urgent` 0.97, `frustration`
  1.46 (entre "civil" y "enojado"), 7.9 s en frío (carga del modelo), ~0.2 s
  en caliente.
- `router/systemone.py`: `ollama` es ahora el primer proveedor del cascade
  (`JEV_PROVIDER_ORDER=ollama,typesafe,openrouter`, `JEV_LOCAL_MODEL`
  default `tev1:4b-q4_K_M`). Un `model` explícito que empiece con `jev`
  va sólo a los proveedores cloud; cualquier otro se trata como tag local.
  La respuesta lleva `x_router.local: true`.
- `nimble` (9B, 9.5 GB) NO se bajó: con 16 GB de disco libre y qwen3.5:9b
  (6.6 GB) ya cargado, es apretado. Si se quiere calidad máxima local:
  `ollama pull nimble` y `JEV_LOCAL_MODEL=nimble` en `.env`.
- ngrok AI Gateway (newsletter 2026-10-01) también sirve Jev, pero su
  quickstart exige comprar ≥ USD 5 de créditos (plan gratis: USD 1 de
  crédito inicial en early access) y el catálogo público aún no lista
  TypeSafe — misma categoría que OpenRouter (pago), sin ventaja sobre el
  backend local. No integrado.

## 2026-10-11 — Liquid AI d1: primer modelo de decisión abierto que compite con Jev (hallado por model-scout)

Liquid AI lanzó **d1** el 2026-09-29 ("our first decision model. It's the
first model to outperform Jev on Hugging Face's Decision Index", x.com/
liquidai), agregó visión el 2026-10-05 (liquid.ai/blog/d1-decision-model) y
el 2026-10-07 publicó pesos abiertos (liquid.ai/blog/d1-open):

| Modelo | Base | Tamaño | GGUF | Licencia | Decision Index v0.2.1 |
|---|---|---|---|---|---|
| `LiquidAI/d1-3B` | LFM2.5-VL-3B (texto+imagen), 3.12B | Q4_K_M **1.67 GB**, Q8_0 2.87 GB, BF16 5.4 GB | `LiquidAI/d1-3B-GGUF` (arch `lfm2`) | LFM Open License v1.0 | **48.57** ("best under 10B"; Decider 35B-A3B 47.11, Winnow-12B 50.02) |
| `LiquidAI/d1-omni-600M` | LFM2.5-Encoder-350M + visión + audio, experimental | ~600M | `LiquidAI/d1-omni-600M-GGUF` | LFM Open License v1.0 | 15.95 |

Media de 7 datasets de texto (tabla 1 del blog): d1-3B 82.9, Decider 4B
81.1, d1-omni-600M 78.4, Decider 2B 77.1. Latencia publicada: 8 ms/decisión
en RTX 4090. **No hay score publicado de tev1 ni nimble en el Decision Index**
(el leaderboard huggingface.co/spaces/multimodalart/jev-decision-index es
JS-rendered y no se pudo leer sin browser; la ficha de nimble reporta 75.7%
en 13 datasets públicos — otro conjunto, no comparable directo).

Licencia (huggingface.co/LiquidAI/d1-3B/blob/main/LICENSE, liquid.ai/
lfm-license): Apache 2.0 modificada — uso comercial libre **sólo por debajo
de USD 10M de facturación anual**, sin copyleft, redistribución y fine-tune
permitidos, terminación automática por incumplimiento. Para este proyecto
(uso propio) no es restricción.

Dónde corre:
- **llama.cpp**: soporte día uno (`llama-server -hf LiquidAI/d1-3B-GGUF:Q8_0`,
  `/v1/systemone`). El post de ggml-org "Decision Models in llama.cpp"
  (2026-10-02) lista Julia-1, Laya, Kev-4B, lev, OpenJev, Clef — d1 se sumó
  después.
- **Ollama**: la ficha HF da `ollama run hf.co/LiquidAI/d1-3B-GGUF:Q4_K_M`.
  NO está en ollama.com/library (`/library/d1` 404; `search?c=decision`
  sigue con clef, clef-flash, laya, nimble, tev1). Sin versión mínima
  publicada — hay que verificar que 0.35.0 sirva `lfm2` en `/v1/systemone`.
- **API cloud**: `api.liquid.ai/decisions/v1/systemone` (`d1` pago USD 0.04/
  Mtok in; `d1:free` listado pero 402 sin key), OpenRouter `liquid/d1` y
  Vercel AI Gateway (pagos). Ver `plans/new-cloud-providers.md`.

Criterio del skill: un modelo de decisión local nuevo entra como candidato a
`JEV_LOCAL_MODEL` si cabe en 16 GB junto a un chat model de 7-9B (**sí:
1.67 GB vs 2.7 GB de tev1:4b-q4_K_M**) o mejora claramente la calidad
publicada de tev1/nimble (**sin dato comparable**; el único número común con
nuestro cascade es "outperforms Jev", afirmación del vendor sin tabla). Por
eso d1-3B es **candidato, no reemplazo**: hay que correr `plans/
jev-example.json` contra ambos y comparar probabilidades.

Prueba local 2026-10-11 (Ollama 0.35.0, Mac en batería 13 %):
- `ollama pull hf.co/LiquidAI/d1-3B-GGUF:Q4_K_M` OK (2.26 GB en disco: el
  GGUF de 1.67 GB más el proyector de visión; Ollama lo cataloga como
  `lfm2`, "2.7B", capabilities `tools, thinking, completion, vision` — es
  decir, lo trata como modelo de CHAT, no de decisión).
- `POST /v1/systemone` con `model: hf.co/LiquidAI/d1-3B-GGUF:Q4_K_M` →
  **HTTP 400** `model ... is not supported by System One; use a local Nimble
  or Tev GGUF model`. Ollama 0.35.0 sólo acepta las familias que conoce
  (tev1, nimble, clef desde 0.35.1); las notas de release hasta v0.40.3-rc0
  no mencionan d1/LFM2. Modelo borrado tras la prueba (`ollama rm`) para
  devolver los 2.3 GB; re-bajar es un comando.
- Upstream: llama.cpp ya lo soporta (PRs ggml-org/llama.cpp #30110 d1-3B y
  #30114 d1-omni-600M, mergeados 2026-10-09); en Ollama hay pedido abierto
  (ollama/ollama#18890 "Request to add d1-3B and d1-omni-600M", 2026-10-09)
  y un PR abierto que actualiza llama.cpp a b11521 "for decision models"
  (ollama/ollama#18917, 2026-10-11) — probablemente el vehículo. Re-chequear
  cada auditoría; cuando una release estable lo incluya, repetir la prueba.

**Comparación independiente — Decision Index 0.3.1** (huggingface.co/spaces/
multimodalart/jev-decision-index, `data/v03.json` generado 2026-10-10, 117
modelos, columna "pub" = suite pública; la nota del vendor "outperforms Jev"
NO se sostiene en este board):

| Modelo | Pub | Rank | Tamaño local |
|---|---|---|---|
| Jev (jev-1.13.0, TypeSafe, cerrado) | 57.96 | #11 | — |
| Bespoke Nimble 9B v3 | 57.19 | #13 | `nimble:9b-q4_K_M` ~9.5 GB (la página de ollama.com menciona v2 y V3; verificar cuál sirve el tag) |
| **LiquidAI d1-3B** | **48.99** | #34 | 1.67 GB GGUF (no corre en Ollama 0.35 — ver arriba) |
| Decider 4B | 41.19 | #49 | — |
| Together Tev1 4B (= `tev1:4b-q4_K_M`, nuestro default) | 29.51 | #75 | 2.7 GB |
| Strands Decider 2B | 25.41 | #84 | PR ollama#18748 abierto |
| d1-omni-600M | 17.9 | #95 | — |
| Together Tev1 0.8B | 13.1 | #101 | 812 MB |
| Laya | 6.19 | #111 | — |

Conclusión: d1-3B es **+19.5 puntos sobre tev1:4b** con 1 GB menos de disco
— el mejor candidato a `JEV_LOCAL_MODEL` hasta hoy, pero **bloqueado por
Ollama** (no por el modelo). Alternativas hoy mismo: (a) `nimble:9b-q4_K_M`
(≈ Jev en el índice, 9.5 GB, apretado en 16 GB con qwen3.5:9b cargado — ya
documentado el 2026-10-01); (b) servir d1-3B con `llama-server -hf
LiquidAI/d1-3B-GGUF:Q4_K_M` en otro puerto y apuntar `router/systemone.py`
a él como proveedor `llamacpp` (mismo esquema System One; sin integrar —
decide José). Sin cambios en `DEFAULT_LOCAL_MODEL`.

### 2026-10-12 — seguimiento del bloqueo

- Ollama **v0.40.3 ya es stable** (2026-10-11T01:39Z) pero **no incluye el PR #18917** (bump de llama.cpp "for decision models"): sigue abierto, mergeable, último commit 2026-10-12T04:04Z; `main` está 0 commits por delante de v0.40.3. d1-3B sigue sin poder probarse en Ollama. Sin cambio en `DEFAULT_LOCAL_MODEL`.
- Nuevo nombre revisado y descartado: **SemIf** (Qwen3.5-4B base, Apache-2.0, sólo quants MLX comunitarios, sin GGUF ni tag en Ollama). Un post de LinkedIn lo ponía "0.7 detrás de Jev"; el Decision Index 0.3.1 público lo tiene en **26.5 #81, por debajo de tev1-4b (29.51 #75)**. No es candidato.
- El mismo board (columna pub) tiene arriba a Perplexity Decider v1.1 27B (62.25 #2) y varios deciders de 26-31B sobre Gemma 4 en 55-60: todos demasiado grandes para 16 GB junto a un chat model. La vía d1-3B sigue siendo la única mejora realista.
