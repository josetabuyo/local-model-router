# Nuevos proveedores cloud de LLM gratis

## Gemini — INTEGRADO 2026-08-24

Agregado como 5to proveedor (`gemini`) tras el incidente de Pulpo/Luganense
del 2026-08-24: Groq/NVIDIA/OpenRouter fallaron los tres al mismo tiempo
(cuota agotada, modelo muerto, rate-limit), dejando el cascade cloud
completo caído. Gemini es un proveedor con infraestructura y cuota
totalmente independiente de los otros tres — reduce el riesgo de que un
solo incidente tumbe todo el cascade cloud.

- `benchmark/providers/gemini_provider.py` — mismo patrón que groq/openrouter.
- `router/dispatcher.py` — `_call_gemini`, base
  `https://generativelanguage.googleapis.com/v1beta/openai`.
- `router/registry.py` — rank de velocidad 2 (junto a NVIDIA; sin datos de
  latencia medidos todavía).
- `rankings/cloud.yaml` — agregado a `multilingual`, `instruction`, `context`
  (las categorías más ligadas al clasificador de Luganense y a resiliencia
  de contexto largo). No agregado a las otras 5 categorías — no hay
  necesidad urgente ahí y evita inflar el cascade sin justificación.
- Modelos: `gemini-3.1-flash-lite` (15 RPM / 1,000 RPD, el más generoso) y
  `gemini-3.5-flash` (10 RPM / 250 RPD, mejor calidad, contexto 1,048,576
  tokens confirmado).
- `GEMINI_API_KEY` ya está en `.env` (confirmado 2026-08-27) — probes en vivo
  contra `gemini-3.1-flash-lite` y `gemini-3.5-flash` devolvieron 200 OK.
  Proveedor activo en el cascade, no pendiente.

## Cerebras — EVALUADO, RECHAZADO 2026-08-24

Su free tier sin tarjeta terminó. Ahora pide método de pago a cambio de
$5 de crédito que expira en 30 días — no es sostenible ni gratis en el
sentido que usa el resto de este cascade (NVIDIA/Groq/OpenRouter/Gemini son
los cuatro sin tarjeta). No integrado. Si el free tier sin tarjeta vuelve en
el futuro, recheck.

## No integrados (evaluados, no encajan)

- Mistral — free tier confirmado pero sin diferencial claro frente a lo que
  ya cubre NVIDIA NIM en las categorías actuales; no hay urgencia.
- Together AI, Vercel AI Gateway, Cloudflare AI Gateway, Requesty, Portkey,
  LiteLLM, Kong AI Gateway — son gateways/agregadores, no proveedores de
  modelo directo; no aportan modelos gratis nuevos, solo enrutan a los que ya
  tenemos o a proveedores pagos. Fuera de alcance de este proyecto (el router
  ya es el propio agregador).

## SambaNova — CANDIDATO SIN VERIFICAR, 2026-08-27 (revisado 2026-09-02)

Encontrado en búsqueda web abierta (blogs agregadores, no fuente primaria):
free tier sin tarjeta, 200,000 tokens/día por modelo. No verificado en vivo
todavía — este proyecto tiene política de no confiar en specs de blogs SEO
sin cruzarlas contra la fuente primaria (docs.sambanova.ai / cloud.sambanova.ai).
Próximo paso si se decide evaluar: confirmar en la doc oficial que sigue sin
pedir tarjeta y qué modelos sirve gratis, antes de proponer integración.

## Cloudflare Workers AI — CANDIDATO SIN VERIFICAR, 2026-09-21

Encontrado en búsqueda web abierta (openrouter.ai/blog y varios agregadores,
2026-09-21) como uno de los proveedores con free tier sin tarjeta más citados
junto a Gemini/Groq — pero es "Workers AI" (hosting de modelos, serverless
inference), NO "Cloudflare AI Gateway" (ya descartado arriba como gateway/
router puro, sin modelos propios). No confundir los dos productos.
No verificado en vivo todavía — antes de evaluar integración hay que
confirmar en la fuente primaria (developers.cloudflare.com/workers-ai) qué
modelos sirve gratis, límites reales (neurons/día) y si de verdad no pide
tarjeta, en vez de confiar en los agregadores SEO que lo mencionan. Si se
confirma un free tier real: API es OpenAI-compatible (mismo patrón que
groq/openrouter/gemini providers), integración debería ser directa si el
usuario aprueba agregar la API key nueva.

Revisión 2026-09-02: se chequeó cloud.sambanova.ai/pricing directamente —
esa página sólo muestra pricing pago por token, sin mención de free tier.
Inconcluso (el free tier podría estar documentado en otra parte del sitio,
no necesariamente no existe) — se mantiene como "sin verificar", no se
promueve ni se descarta. Pendiente para un futuro pase con más tiempo para
recorrer el resto de la doc.

## OVHcloud AI Endpoints — VERIFICADO EN VIVO, PROPUESTA PENDIENTE 2026-09-25

Encontrado vía github.com/mnfst/awesome-free-llm-apis y verificado contra la
fuente primaria + llamadas reales el 2026-09-25.

**Lo que se confirmó:**
- Tier anónimo real: **sin API key y sin cuenta**. `POST
  https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions` con
  `model: Qwen3.8-27B` → 200 OK en 1.7s, respuesta correcta. API
  OpenAI-compatible (mismo patrón que groq/openrouter/gemini providers);
  el modelo devuelve un campo extra `reasoning` junto a `content`.
- Catálogo (`GET /v1/models`, sin key): gpt-oss-120b, gpt-oss-20b,
  Qwen3.8-27B, Qwen3.6-27B, Qwen3.5-397B-A17B, Qwen3.5-9B,
  Meta-Llama-3_3-70B-Instruct, Mistral-Small-3.2-24B-Instruct-2506,
  Mistral-Nemo-Instruct-2407, Mistral-7B-Instruct-v0.3,
  Qwen3-Coder-30B-A3B-Instruct, Qwen2.5-VL-72B-Instruct, más
  embeddings (bge-m3, Qwen3-Embedding-8B), whisper-large-v3 y TTS.
- Límite anónimo: **2 requests/minuto**. Doc oficial
  (docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/
  ai-endpoints-getting-started): "Anonymous: 2 requests per minute, per IP
  and per model". Confirmado en vivo con headers del 429: `ratelimit-limit:
  2`, `x-ratelimit-limit-minute: 2`, `retry-after: 27`. Matiz observado:
  una llamada a gpt-oss-120b dio 429 inmediatamente después de dos a
  Qwen3.8-27B, o sea que en la práctica el bucket parece global por IP,
  no por modelo — asumir 2 RPM totales.
- Tier autenticado: 400 RPM por proyecto y modelo, pero la API key
  **requiere método de pago** ("Access keys created from Public Cloud
  projects in Discovery mode (without a payment method) cannot use the
  service"). Mismo descalificador que Cerebras — no es "gratis sin tarjeta".

**Por qué NO se integró en esta auditoría:**
2 RPM es demasiado poco para un tramo normal del cascade (Groq da 30 RPM,
NIM 40, OpenRouter 20). Un bench de 8 categorías lo agotaría en la primera
ronda. Además, hoy Qwen3.8-27B y gpt-oss-120b/20b ya están cubiertos vía
Groq con 15x más cuota.

**Por qué igual vale la pena considerarlo:**
Es el único proveedor encontrado hasta ahora con cero configuración (sin
key, sin cuenta, sin tarjeta) e infraestructura independiente de los 4
actuales, hosteado en la UE. Eso lo hace un candidato ideal a **fallback de
último recurso**: si Groq/NIM/OpenRouter/Gemini fallan todos a la vez
(incidente Luganense 2026-08-24), 2 RPM es mejor que cero, y no puede
"morir" por cuota agotada ni por key expirada.

**Pasos de integración si el usuario aprueba** (~1 hora):
1. `benchmark/providers/ovh_provider.py`: copiar `groq_provider.py`, base
   `https://oai.endpoints.kepler.ai.cloud.ovh.net/v1`, sin header
   `Authorization` (o opcional si algún día hay key). `FREE_MODELS =
   ["Qwen3.8-27B", "gpt-oss-120b", "gpt-oss-20b"]`. Manejar 429 con
   `retry-after` (el header viene, ~27-30s) — o mejor, NO reintentar y
   dejar que el cascade siga, porque esperar 30s bloquea el router.
2. `router/dispatcher.py`: `_call_ovh`, mismo patrón que `_call_gemini`.
3. `router/registry.py`: `_PROVIDER_SPEED_RANK["ovh"] = 9` (último) para
   que siempre quede al final del cascade en toda categoría.
4. `rankings/cloud.yaml`: agregar como ÚLTIMO slot en `instruction`,
   `multilingual`, `coding` (las categorías donde Qwen3.8-27B / gpt-oss
   ya están validados en este archivo vía Groq). No en las demás.
5. Sin cambios en `.env` — no hay key.
6. Test: un `curl` anónimo por modelo + correr `tests/` para el registry.

Riesgo: bajo (sin secretos nuevos, siempre último en el cascade). Decisión
del usuario — no se integra a ciegas.

## Siguiente paso

Cascade actual (NVIDIA/Groq/OpenRouter/Gemini) ya tiene 4 proveedores
independientes sin tarjeta — no hay urgencia de agregar un 5to salvo que se
repita un incidente de caída simultánea como el de Luganense (2026-08-24).
