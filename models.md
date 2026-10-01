# Inventario de modelos — cloud + local

<!-- GENERADO por scripts/render_models.py desde rankings/*.yaml — no editar a mano.
     Regenerar: uv run scripts/render_models.py -->

Actualizado: 2026-10-01 · Máquina: Apple Silicon, 16 GB RAM.
Fuente de verdad: `rankings/cloud.yaml` (cloud, con el log diario de auditorías
de `/model-scout` en sus `NOTE`) y `rankings/local.yaml` (benchmarks propios de Ollama).

## 1. Cascade cloud por categoría (gratis, vía el router)

Orden de proveedores por defecto en `best:<categoría>`: el que lista cada fila.
`fastest:` reordena por velocidad medida (Groq primero), `cheapest:` agrega los
pagos al final.

| Categoría | Slot 0 | Resto del cascade (en orden) |
|---|---|---|
| `reasoning` | `nvidia/z-ai/glm-5.3` | `groq/openai/gpt-oss-120b`, `groq/openai/gpt-oss-20b`, `openrouter/google/gemma-4-31b-it:free`, `openrouter/google/gemma-4-26b-a4b-it:free`, `openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`, `openrouter/nvidia/nemotron-3-super-120b-a12b:free` |
| `coding` | `nvidia/z-ai/glm-5.3` | `groq/openai/gpt-oss-120b`, `groq/openai/gpt-oss-20b`, `openrouter/poolside/laguna-s-2.1:free`, `openrouter/cohere/north-mini-code:free`, `openrouter/google/gemma-4-31b-it:free`, `openrouter/nvidia/nemotron-3-super-120b-a12b:free` |
| `math` | `nvidia/z-ai/glm-5.3` | `groq/openai/gpt-oss-120b`, `groq/openai/gpt-oss-20b`, `openrouter/google/gemma-4-31b-it:free`, `openrouter/nvidia/nemotron-3-super-120b-a12b:free` |
| `summarization` | `nvidia/z-ai/glm-5.3` | `groq/openai/gpt-oss-120b`, `groq/openai/gpt-oss-20b`, `openrouter/google/gemma-4-31b-it:free`, `openrouter/nvidia/nemotron-3-super-120b-a12b:free` |
| `instruction` | `groq/qwen/qwen3.8-27b` | `openrouter/google/gemma-4-31b-it:free`, `gemini/gemini-3.1-flash-lite` |
| `multilingual` | `groq/openai/gpt-oss-20b` | `nvidia/z-ai/glm-5.3`, `openrouter/google/gemma-4-31b-it:free`, `gemini/gemini-3.1-flash-lite` |
| `code_debug` | `nvidia/z-ai/glm-5.3` | `groq/openai/gpt-oss-120b`, `groq/openai/gpt-oss-20b`, `openrouter/poolside/laguna-s-2.1:free`, `openrouter/cohere/north-mini-code:free`, `openrouter/google/gemma-4-31b-it:free`, `openrouter/nvidia/nemotron-3-super-120b-a12b:free` |
| `context` | `nvidia/z-ai/glm-5.3` | `groq/openai/gpt-oss-120b`, `groq/openai/gpt-oss-20b`, `openrouter/nvidia/nemotron-3-super-120b-a12b:free`, `openrouter/google/gemma-4-31b-it:free`, `gemini/gemini-3.5-flash` |

## 2. Modelos cloud gratis — dónde rankean

| Modelo | Proveedor | Categorías (categoría#slot) | Contexto | Arena ELO |
|---|---|---|---|---|
| `gemini/gemini-3.1-flash-lite` | gemini | instruction#2, multilingual#3 | — | — |
| `gemini/gemini-3.5-flash` | gemini | context#5 | 1,048,576 | — |
| `groq/openai/gpt-oss-120b` | groq | reasoning#1, coding#1, math#1, summarization#1, code_debug#1, context#1 | — | — |
| `groq/openai/gpt-oss-20b` | groq | reasoning#2, coding#2, math#2, summarization#2, multilingual#0, code_debug#2, context#2 | — | — |
| `groq/qwen/qwen3.8-27b` | groq | instruction#0 | — | — |
| `nvidia/z-ai/glm-5.3` | nvidia | reasoning#0, coding#0, math#0, summarization#0, multilingual#1, code_debug#0, context#0 | 1,048,576 | — |
| `openrouter/cohere/north-mini-code:free` | openrouter | coding#4, code_debug#4 | 256,000 | — |
| `openrouter/google/gemma-4-26b-a4b-it:free` | openrouter | reasoning#4 | 262,144 | 1438 |
| `openrouter/google/gemma-4-31b-it:free` | openrouter | reasoning#3, coding#5, math#3, summarization#3, instruction#1, multilingual#2, code_debug#5, context#4 | 262,144 | 1451 |
| `openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | openrouter | reasoning#5 | 256,000 | — |
| `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | openrouter | reasoning#6, coding#6, math#4, summarization#4, code_debug#6, context#3 | 1,000,000 | 1343 |
| `openrouter/poolside/laguna-s-2.1:free` | openrouter | coding#3, code_debug#3 | 1,000,000 | — |

## 3. Modelos cloud pagos (sólo vía `cheapest:<categoría>`)

_(ninguno)_

## 4. Modelos locales (Ollama)

Benchmark propio — ver fechas y archivos de resultados en la cabecera de
`rankings/local.yaml`. `qwen3.5:9b` (daily driver interactivo desde 2026-08-12)
se midió el 2026-10-01 con thinking activado: correcto en 7/8 tareas pero con
1,200–2,100 tokens de razonamiento por tarea (30–130 s), y timeout en
`multilingual`; queda último en cada categoría hasta re-medirlo con `think=false`.

| Modelo | Categorías donde gana (slot 0) | tok/s (medido) | Nota |
|---|---|---|---|
| `qwen2.5:7b` | reasoning, summarization, instruction, math, multilingual | 21.3 |  |
| `deepseek-r1:8b` | context | 20.9 |  |
| `qwen2.5:14b` | — | 6.5 | eliminado de Ollama |
| `qwen3.5:9b` | — | 17.3 |  |
| `qwen2.5-coder:7b` | coding, code_debug | 13.4 |  |

## 5. Modelos de decisión (Jev-style, `POST /v1/systemone`)

| Backend | Modelo | Estado |
|---|---|---|
| `ollama` (local, Ollama ≥ 0.35) | `tev1:4b-q4_K_M` (2.7 GB, Together AI) — `nimble` (9B, 9.5 GB, Bespoke Labs) opcional | instalado, primero en el cascade |
| `typesafe` (Jev real) | `jev-latest` (= jev-1.13) | necesita `TYPESAFE_API_KEY` |
| `openrouter` | `jev-1.13` vía `/api/v1/systemone` | pago, necesita créditos |
| emulación | `best:instruction` forzado a JSON | último recurso, `x_router.emulated: true` |
