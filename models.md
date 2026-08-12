# Inventario de modelos — cloud + local

Máquina: MacBook (darwin arm64) · Actualizado: 2026-08-12

Este doc es la foto legible-por-humanos de lo que hay en `rankings/cloud.yaml` (fuente de
verdad para el router) y `rankings/local.yaml` (benchmarks propios de Ollama). Si difieren,
ganan los `.yaml` — actualizar ahí primero, después reflejar acá.

---

## 1. Modelos cloud (gratis, vía el router)

Cascada por categoría: **NVIDIA NIM → Groq → OpenRouter (free)**. Todo lo de abajo es
gratis; los modelos `paid: true` (fallback de `cheapest:`) están en la sección 4.

| Modelo | Proveedor | Categorías donde gana (slot 0) | Contexto | Benchmark clave | Notas |
|---|---|---|---|---|---|
| `z-ai/glm-5.2` | NVIDIA NIM | coding, code_debug, context | 1M | SWE-bench Pro 62.1, Terminal-Bench 81.0 | MIT, top open-weight coding |
| `deepseek-ai/deepseek-v4-flash` | NVIDIA NIM | coding, code_debug | 1M | Terminal-Bench 82.7 | 13B activos, le gana a glm-5.2 y a su propio v4-pro en agentic coding |
| `deepseek-ai/deepseek-v4-pro` | NVIDIA NIM | reasoning, math, context | 1M | arena ELO 1370 | mantiene reasoning/math, reemplazado por flash en coding |
| `moonshotai/kimi-k2.6` | NVIDIA NIM | reasoning, math, summarization, multilingual | — | arena ELO 1461 | el ELO más alto de la cascada NIM |
| `thinkingmachines/inkling` | NVIDIA NIM | reasoning, instruction | 1M | SWE-bench 77.6, #12 Instruction Following | 975B MoE / 41B activos, Apache 2.0, multimodal |
| `meta/muse-glimmer-30b` | NVIDIA NIM | reasoning, instruction, coding, code_debug | 131K | MCP-Atlas (agentic) 75.5 | **nuevo 2026-08-10**, primer modelo agéntico open-weight de Meta, iguala a Kimi K2.5 (1T params) con 33x menos |
| `minimaxai/minimax-m3` | NVIDIA NIM | summarization, context | 1M | arena ELO 1447 | mejor para documentos muy largos |
| `openai/gpt-oss-120b` | Groq | reasoning, coding, math, summarization, code_debug, context | — | ~o4-mini | 500 tok/s en LPU |
| `qwen/qwen3.6-27b` | Groq | reasoning, coding, math, code_debug, multilingual | — | GPQA 87.8, AIME 94.1, LiveCodeBench 83.9 | el "todoterreno" de Groq |
| `openai/gpt-oss-20b` | Groq | reasoning, coding, math, code_debug, context, multilingual | — | — | **reemplaza a `llama-3.1-8b-instant`, que Groq apaga el 16/08/2026** |
| `llama/llama-4-scout-17b-16e-instruct` | Groq | instruction | — | — | reemplazo para `instruction` (no-reasoning, no como gpt-oss) |
| `nvidia/nemotron-3.5-lightning:free` | OpenRouter | reasoning | 131K | +30% velocidad agentic (PinchBench) | **nuevo 2026-08-11**, reemplaza a `ling-3.0-flash:free` (promo vencida) |
| `google/gemma-4-31b-it:free` | OpenRouter | varias (fallback) | 262K | arena ELO 1451 | fallback de calidad en casi todas las categorías |
| `poolside/laguna-s-2.1:free` | OpenRouter | coding, code_debug | 1M | SWE-bench Multilingual 78.5 | 118B MoE / 8B activos, usar en modo thinking |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | OpenRouter | context | 1M | — | el más grande del free tier de OpenRouter |

**Últimos cambios (2026-08-12):**
- 🔴 **Urgente, ya aplicado**: Groq apaga `llama-3.1-8b-instant` (y `llama-3.3-70b-versatile`, sin uso acá) el **16/08/2026**. Reemplazado en 8 categorías por `openai/gpt-oss-20b` (recomendación oficial de Groq), excepto en `instruction` que fue a `llama-4-scout-17b-16e-instruct` para no meter un modelo con razonamiento donde el `<think>` block rompe respuestas cortas.
- 🔴 `inclusionai/ling-3.0-flash:free` — la promo que ya veníamos marcando como time-limited venció el 03/08 tal cual estaba anotado. Confirmado fuera del catálogo free en vivo. Reemplazado en `reasoning` por `nemotron-3.5-lightning:free`; sacado de `instruction` sin reemplazo (aún sin verificar si tiene traza de razonamiento).
- ✅ Agregado `meta/muse-glimmer-30b` (Muse Glimmer, Meta, 10/08/2026) a 4 categorías.
- Sin más EOLs detectados en NVIDIA NIM ni en el resto del catálogo free de OpenRouter (16 slugs, verificado en vivo).

---

## 2. Servicios alternativos evaluados (no integrados)

Investigado el 2026-08-12 para ver si conviene sumar otro eslabón al cascade:

| Servicio | ¿Gratis de verdad? | Veredicto |
|---|---|---|
| **Cerebras Cloud** | Sí, sin tarjeta. gpt-oss-120b, GLM-4.7. Muy rápido (wafer-scale). | Interesante pero **contexto tope 8K** en el free tier — limita mucho. Evaluar si aparece un caso de uso corto/rápido. |
| **Google AI Studio (Gemini)** | Sí, sin vencimiento. Flash-Lite ~15-30 RPM/1000 RPD. Endpoint OpenAI-compatible (`/v1beta/openai/`). | **Candidato serio** para un rung nuevo — propietario pero límites decentes. |
| **Mistral La Plateforme** | Tier "Experiment" sin tarjeta, ~1B tokens/mes. Incluye Mistral Large + Codestral. | **Candidato** — el techo mensual es alto, pero no hay RPM/TPM público, hay que probarlo en vivo. |
| **SambaNova Cloud** | Free tier existe pero es tacaño (ej. 20 RPM/20 RPD por modelo) sin tarjeta. | Marginal — no mucho mejor que OpenRouter free. |
| **Cloudflare Workers AI** | Sí, 10 000 "Neurons"/día sin tarjeta. | Marginal — el presupuesto diario equivale a ~15-25 llamadas, muy poco para un cascade real. |
| **Together AI / Fireworks AI / DeepInfra** | No — solo créditos de prueba que se agotan. | Descartados. |

**Conclusión:** no hay nada urgente para sumar, pero **Gemini free tier** y **Mistral La Plateforme**
son los dos candidatos con mejor relación límites/utilidad si en algún momento se quiere un 4to
proveedor en la cascada.

---

## 3. Modelos locales (Ollama)

**Hardware real de esta máquina: 16 GB RAM unificada, 10 cores (8P+2E), probablemente M1 Pro.**
Esto importa mucho más que "cuánto pesa el modelo en disco": en un Mac la RAM es *unificada*
(CPU+GPU comparten el mismo pool), así que macOS + apps + Ollama compiten por los mismos 16 GB.
Regla práctica: dejar ~5-6 GB para el sistema deja un presupuesto real de **8-10 GB para el
modelo** en uso cómodo; hasta ~13 GB es "apretado pero anda"; por encima de eso, riesgo de swap
o de que Ollama directamente falle al cargar. Esto descarta de entrada a varios modelos que
había anotado antes como candidatos (gemma4:26b, qwen3.6:27b, muse-glimmer:30b — todos 15-17 GB):
técnicamente "gratis" y open-weight, pero no entran cómodos en esta máquina en particular.

### Instalados y benchmarkeados (`rankings/local.yaml`, corrida propia 2026-06-20/07-27)

| Modelo | Tamaño disco | tok/s (bench) | Gana en | Nota |
|---|---|---|---|---|
| `qwen2.5:7b` | ~4.7 GB | 16-26 tok/s | reasoning, summarization, instruction, math, multilingual | el default, rápido y confiable |
| `qwen2.5-coder:7b` | ~4.7 GB | 11-16 tok/s | coding, code_debug | fine-tune de código, mismo footprint que qwen2.5:7b, mejor HumanEval |
| `deepseek-r1:8b` | ~5.2 GB | 19-22 tok/s (pero CoT infla el wall-clock 3-10x) | context | el único que responde bien en la tarea de retención de contexto; para todo lo demás el CoT lo hace lento |
| ~~`qwen2.5:14b`~~ | — | 1.3-8.8 tok/s | — | **eliminado 2026-06-21**, no competitivo en ninguna categoría |

`models.md` (versión vieja) decía que solo había `gemma4:e4b` instalado — **eso ya no es así**;
`gemma4:e4b` ni siquiera está instalado hoy. Los tres de arriba son los reales, confirmado con
`ollama list`. Son también los únicos con benchmark propio (tok/s + wall-clock medidos en esta
máquina) — todo lo de abajo son specs/benchmarks publicados por los fabricantes o terceros, sin
verificar acá todavía.

### Candidatos trending (agosto 2026), por nivel de riesgo de memoria

**Tier A — mismo footprint que lo instalado, sin riesgo (5-7 GB):**

| Modelo | Pull | Disco (Q4) | Contexto | Por qué |
|---|---|---|---|---|
| `qwen3.5:9b` | `ollama pull qwen3.5:9b` | 6.6 GB | 256K, multimodal (imagen+video) | según reportes iguala o supera a gpt-oss-120b (13x más grande) en varios benchmarks de lenguaje/agentic; índice agéntico 55.5 |
| `ministral-3:8b` | `ollama pull ministral-3:8b` | 6.0 GB | multimodal (visión) | AIME24 86%, GPQA Diamond 66.8%, fuerte en idiomas europeos — buen candidato para multilingual |

**Tier B — estirando el presupuesto, pero razonable (7-9 GB):**

| Modelo | Pull | Disco (Q4) | Contexto | Por qué |
|---|---|---|---|---|
| `gemma4:12b` | `ollama pull gemma4:12b` | 7.6 GB | 256K, multimodal | MMLU Pro 77.2, GPQA Diamond 78.8, AIME 77.5 — explícitamente posicionado por Google para laptops de 16GB |
| `JetBrains/mellum2-thinking` (Mellum2-12B-A2.5B) | vía HF GGUF, no está en `ollama.com/library` todavía | 7.0 GB (MXFP4) / 8.1 GB (Q4_K_M) | — | especialista en código, MoE 12B/2.5B activos → rápido pese al tamaño nominal. LiveCodeBench v6 69.9, mejor que lo que tenemos hoy para coding. **Requiere importar el GGUF manualmente (`ollama create` con Modelfile), no hay pull directo todavía.** |

**Tier C — al límite, solo si se cierra todo lo demás (~13 GB):**

| Modelo | Pull | Disco | Nota |
|---|---|---|---|
| `gpt-oss:20b` | `ollama pull gpt-oss:20b` | ~13 GB (MXFP4 nativo) | OpenAI dice que 16GB es el piso "bare minimum" — casi llena toda la RAM, no queda margen para nada más corriendo. No recomendado como daily driver acá. |

**Descartados para esta máquina (15-17+ GB, no entran con margen):** `gemma4:26b` (MoE),
`qwen3.6:27b`, `meta/muse-glimmer-30b`, `qwen3-coder:30b-a3b` (19 GB), `devstral:24b` (14 GB) —
todos buenos modelos, pero pensados para Macs de 24-32GB+ o GPUs dedicadas de 24GB VRAM.

### Embeddings

| Modelo | Pull | Por qué |
|---|---|---|
| `bge-m3` | `ollama pull bge-m3` | reemplazo moderno de `nomic-embed-text`, mejor en MTEB, buen soporte multilingüe/híbrido |
| `mxbai-embed-large` | `ollama pull mxbai-embed-large` | alternativa, buen ranking MTEB en inglés |

### Recomendación concreta

Con el presupuesto de esta máquina, lo que más vale la pena probar (no solo leer specs) es:
1. **`qwen3.5:9b`** — candidato a reemplazar/complementar `qwen2.5:7b` como generalista; mismo
   rango de tamaño, contexto mucho más grande (256K vs el actual), y multimodal.
2. **`gemma4:12b`** — si el benchmark propio confirma los números de reasoning publicados, es
   candidato fuerte para las categorías `reasoning`/`math` donde hoy gana `qwen2.5:7b` por
   default más que por ser claramente el mejor.
3. Coding se queda con `qwen2.5-coder:7b` por ahora — Mellum2 es prometedor pero no tiene pull
   directo en Ollama todavía (hay que armar el Modelfile a mano), no vale la fricción sin antes
   confirmar que el resultado es mejor.

Todo esto son specs publicadas, no medición propia — el paso siguiente lógico es correr el
harness de `rankings/local.yaml` contra `qwen3.5:9b` y `gemma4:12b` para tener números reales
en esta máquina antes de decidir si reemplazan algo.

---

## 4. Modelos pagos (solo vía `cheapest:<categoría>`, último recurso)

| Modelo | Costo in/out por Mtok | Categorías |
|---|---|---|
| `kwaipilot/kat-coder-air-v2.5` | $0.15 / $0.60 | coding, code_debug |
| `moonshotai/kimi-k3` | $3.00 / $15.00 | coding, code_debug |

`kimi-k3` sigue sin listado gratis en NVIDIA NIM ni Groq pese a tener weights abiertos desde
27/07 — recheck periódico, ver `WATCH` note en `cloud.yaml`.

---

## Cómo usar un modelo local

```bash
ollama run qwen2.5:7b
```

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen2.5:7b", "messages": [{"role": "user", "content": "Hola"}]}'
```

### Integración con Pulpo

Prefijo `local:` en el model ID (`local:qwen2.5:7b`). Override con `OLLAMA_BASE_URL`
(default `http://localhost:11434/v1`). Ver `pulpo/_/backend/graphs/nodes/llm.py`.

### Comandos útiles

```bash
ollama list                    # modelos instalados
ollama show <modelo>           # detalles
ollama pull <modelo>           # descargar
ollama rm <modelo>             # eliminar
ollama ps                      # modelos cargados en memoria
```

---

## Próximos pasos

- [ ] Correr el harness propio (`rankings/local.yaml`) contra `qwen3.5:9b` y `gemma4:12b` (Tier
      A/B, entran cómodos en 16GB) para tener números reales antes de reemplazar algo instalado.
- [ ] Si Tier A/B rinde bien, evaluar si vale la fricción de armar el Modelfile para
      `JetBrains/mellum2-thinking` como reemplazo de coding.
- [ ] `gemma4:26b`, `qwen3.6:27b` y `meta/muse-glimmer-30b` quedan descartados para esta máquina
      (16GB) — no re-evaluar salvo upgrade de RAM.
- [ ] Evaluar Gemini free tier y Mistral La Plateforme como 4to eslabón del cascade cloud.
- [ ] Verificar si `nemotron-3.5-lightning:free` tiene traza de razonamiento antes de
      considerarlo para `instruction` u otras categorías sensibles a `<think>` blocks.
- [ ] Recheck `kimi-k3` en NVIDIA NIM (weights abiertos desde 27/07, aún sin listing gratis).
