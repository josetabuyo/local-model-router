---
name: model-scout
description: Auditoría diaria de proveedores cloud de LLM gratis (NVIDIA NIM, Groq, OpenRouter, Gemini), de modelos de decisión Jev-style (TypeSafe, OpenRouter /systemone, Ollama tev1/nimble) y de novedades locales (Ollama, cuantización, modelos runnable en 16GB RAM Apple Silicon). Detecta altas/bajas de modelos, nuevos proveedores gratis, y mejoras de performance/memoria/inteligencia. Actualiza rankings/cloud.yaml, providers/*.py, y memoria del proyecto; commitea y pushea.
---

# /model-scout — auditoría de LLM gratis + novedades locales

Corre en el repo `local-model-router` (este directorio). Objetivo: mantener el cascade
cloud (`rankings/cloud.yaml`, `benchmark/providers/*.py`, `router/registry.py`) y el
inventario de modelos locales (Ollama) al día, sin depender de que alguien lo dispare
a mano.

## 1. Fuentes conocidas — verificación LIVE (no blogs SEO)

Repetir el proceso ya validado en `rankings/cloud.yaml` (ver notas `NOTE 2026-08-xx`
dentro del archivo — es el registro de auditorías previas, leerlo primero):

```bash
# NVIDIA NIM
curl -s https://integrate.api.nvidia.com/v1/models | jq -r '.data[].id'

# OpenRouter (catálogo free, no requiere key)
curl -s https://openrouter.ai/api/v1/models | jq -r '.data[] | select(.id|endswith(":free")) | .id'

# Groq — no tiene listado público sin key; usar console.groq.com/docs/models
# o un chat-completion probe directo a cada modelo en FREE_MODELS
```

**Presupuesto de probes.** OpenRouter limita los modelos `:free` a **50
requests/día por key** (`GET /api/v1/auth/key` → `free_model_daily_requests`).
Cada auditoría gasta ~10; no repetir probes "para confirmar" más de 2 veces
por modelo ni correr la auditoría dos veces el mismo día sin necesidad.
Consultar ese endpoint al inicio y anotar `used/limit` en la nota del día.

**Mac dormido = lecturas falsas.** Maintenance Sleep corta probes a mitad de
camino (HTTP 000 con wall time muy por encima de `--max-time`). El cron ya
corre bajo `caffeinate -s -i`; en una corrida manual, usar lo mismo y anotar
`pmset -g batt` en la nota. Descartar y repetir las lecturas con wall time
absurdo, nunca registrarlas como hang.

Para cada modelo que ya está en `rankings/cloud.yaml` / `FREE_MODELS` de los providers:
hacer una llamada real de chat completion (1 mensaje corto) contra ese modelo.
- 404/410 → dado de baja (EOL), sacarlo.
- 429 → NO sacarlo, es rate-limit de cuota gratis, no un modelo muerto. Documentar.
- 200 → sigue vivo, no tocar.

Para modelos nuevos que aparecen en el listado y no están en el ranking: evaluar si
encajan en alguna categoría (`reasoning`, `coding`, `math`, `code_debug`, `instruction`,
`multilingual`, `summarization`, `context`) y si superan al slot 0 actual de esa
categoría (benchmarks públicos: Arena ELO, SWE-Bench, Terminal-Bench — citar fuente).

### Fuentes de ranking — primaria + respaldo independiente

No usar un solo agregador como única fuente de scores. Consultar siempre:

1. **lmarena.ai (LMArena) directo** — fuente primaria de Arena ELO/leaderboard,
   es la organización que genera el dato. Preferir esto sobre citar
   `lmmarketcap.com`, que es un agregador de LMArena (dato de segunda mano,
   puede estar desactualizado respecto al leaderboard real).
2. **Artificial Analysis (artificialanalysis.ai)** — segundo agregador
   independiente, ya citado en varias notas de `rankings/cloud.yaml` (ej. Kimi
   K3 "#3 on Artificial Analysis"). Usar como respaldo/contraste cuando
   LMArena no tiene el modelo listado todavía (modelos muy nuevos) o para
   confirmar un ranking antes de promover un modelo a slot 0.

Si las dos fuentes discrepan fuerte en el ranking de un modelo, anotar ambos
números y la discrepancia en vez de elegir uno en silencio — dejar que el
usuario decida si importa para el caso de uso.

### Modelos de decisión (Jev-style, `POST /v1/systemone`)

El router expone `/v1/systemone` (ver `router/systemone.py` y
`plans/jev-systemone.md`) con cascade `ollama → typesafe → openrouter`.
Auditar cada día, con el body de `plans/jev-example.json`:

```bash
# Local (Ollama >= 0.35): el modelo pineado en JEV_LOCAL_MODEL (default tev1:4b-q4_K_M)
curl -s localhost:11434/v1/systemone -d "$(jq '. + {model:"tev1:4b-q4_K_M"}' plans/jev-example.json)"
# Catálogo: ¿hay modelos de decisión nuevos o versiones nuevas de tev1/nimble?
#   ollama.com/library/tev1/tags, ollama.com/library/nimble, ollama.com/search?c=decision
# OpenRouter: ¿apareció una variante :free de typesafe/jev-*? (hoy es pago)
curl -s https://openrouter.ai/api/v1/models | jq -r '.data[] | select(.id|test("typesafe|jev")) | "\(.id) \(.pricing.prompt)"'
# TypeSafe directo: versión actual del modelo (jev-1.13 al 2026-10-01) y cambios de acceso
#   docs.typesafe.ai/introduction/quickstart, typesafe.ai/blog
```

Criterio: un modelo de decisión local nuevo entra como `JEV_LOCAL_MODEL`
candidato sólo si cabe en 16 GB junto a un chat model de 7-9B (≤ ~5 GB) o
mejora claramente la calidad publicada de `tev1`/`nimble` (citar fuente).
Si Jev aparece gratis en algún proveedor sin tarjeta, es cambio de cascade:
avisar al usuario, no pinear solo.

## 2. Fuentes nuevas — búsqueda web abierta

Buscar (WebSearch/WebFetch) específicamente:
- Nuevos proveedores de LLM gratis o con free tier generoso (tipo NVIDIA NIM,
  Groq, OpenRouter, Cerebras, SambaNova, etc.) — no asumir que la lista de 3
  proveedores actuales es definitiva.
- Releases de modelos open-weight de la última semana (Meta, DeepSeek, Qwen,
  Z.ai/GLM, Moonshot/Kimi, MiniMax, Mistral, etc.) que puedan aparecer gratis
  en alguno de los proveedores ya integrados o en uno nuevo.
- Novedades técnicas relevantes para uso LOCAL en esta máquina (Apple Silicon,
  16GB RAM — ver `plans/` y memoria del proyecto para el perfil de hardware):
  cuantización nueva (GGUF, MLX), modelos que corran más rápido, con menos
  memoria, o con mejor balance calidad/recursos que lo que hay hoy en Ollama.

Cada hallazgo de esta sección necesita fuente citada (URL + fecha) antes de
entrar al ranking — no fabricar scores ni specs.

## 3. Aplicar cambios

- `rankings/cloud.yaml`: agregar una nota fechada (mismo formato que las existentes)
  con qué se encontró, qué se agregó/sacó y por qué, con fuente.
- `models.md`: NO editar a mano — regenerar con `uv run scripts/render_models.py`
  después de cualquier cambio en `rankings/*.yaml` (y commitearlo junto).
- `benchmark/providers/{groq,openrouter}_provider.py`: actualizar `FREE_MODELS` si
  cambió el catálogo vivo.
- `benchmark/providers/nvidia_provider.py`: ídem `FREE_MODELS` cuando cambie el
  pin de NVIDIA NIM en `rankings/cloud.yaml`.
- `router/registry.py`: actualizar `_SPEED_OVERRIDES` si un modelo referenciado ahí
  fue dado de baja o reemplazado.
- `router/systemone.py` (`DEFAULT_LOCAL_MODEL`, `DEFAULT_MODELS`): si cambia el
  modelo de decisión recomendado o el id de Jev en OpenRouter/TypeSafe.
- Si hay un proveedor nuevo viable (free tier real, API compatible OpenAI o fácil de
  adaptar): dejarlo documentado en `plans/` como propuesta con pasos de integración,
  no integrarlo a ciegas sin que el usuario lo revise si implica una API key nueva.
- Memoria del proyecto (`project_benchmark_harness.md`, `project_nvidia_nim.md` o una
  nueva memoria si el hallazgo lo amerita): registrar el resumen del día.

## 4. Si no hay nada nuevo

No forzar cambios. Si la auditoría no encuentra altas, bajas, ni fuentes nuevas,
registrar igual una línea de "chequeado, sin cambios" con fecha en `rankings/cloud.yaml`
para dejar rastro de que corrió (evita re-investigar lo mismo mañana).

## 5. Commit y push

Si hubo cambios de contenido (no solo la línea de "sin cambios"):

```bash
git add rankings/cloud.yaml models.md benchmark/providers/ router/registry.py router/systemone.py plans/
git commit -m "chore(model-scout): auditoría diaria de modelos/proveedores gratis"
git push origin main
```

Si el cambio toca algo con riesgo real (nueva API key requerida, cascade completo
reordenado, un modelo core removido sin reemplazo claro) — no pushear directo,
avisar al usuario primero.

## 6. Reporte

Al terminar, avisar en texto: qué se agregó, qué se dio de baja, qué se evaluó y
se descartó (y por qué), y si hay algo que requiere que el usuario agregue una API
key o tome una decisión. Formato corto, tipo changelog.
