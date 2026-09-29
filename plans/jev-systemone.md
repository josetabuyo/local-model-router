# Jev (TypeSafe System One) en el router — estado 2026-09-27

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

Ollama **v0.35.0** (pre-release, 2026-09-28) agrega modelos de decisión en
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

- El cliente local es 0.21.2 y brew stable es 0.34.2; 0.35 hoy es sólo
  pre-release (instalarla a mano desde GitHub o esperar a brew).
- No está verificado que las probabilidades de tev1/nimble estén calibradas
  igual que las de Jev: Ollama dice "based on", no que sea el mismo modelo.

Pasos propuestos (decide José):

1. Instalar Ollama ≥ 0.35 (pre-release desde GitHub, o `brew upgrade ollama`
   cuando llegue a stable) y `ollama pull tev1:4b-q4_K_M`.
2. Probar `curl localhost:11434/v1/systemone -d @plans/jev-example.json`.
3. Agregar `ollama` como primer proveedor del cascade en `router/systemone.py`
   (antes de `typesafe` → `openrouter`), con el modelo configurable
   (`JEV_LOCAL_MODEL`, default `tev1`), y marcar `x_router.provider` en la
   respuesta para distinguir local de Jev real.
4. Comparar local, emulación y (si aparece la key) Jev real con el mismo body.
