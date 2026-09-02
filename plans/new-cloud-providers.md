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

Revisión 2026-09-02: se chequeó cloud.sambanova.ai/pricing directamente —
esa página sólo muestra pricing pago por token, sin mención de free tier.
Inconcluso (el free tier podría estar documentado en otra parte del sitio,
no necesariamente no existe) — se mantiene como "sin verificar", no se
promueve ni se descarta. Pendiente para un futuro pase con más tiempo para
recorrer el resto de la doc.

## Siguiente paso

Cascade actual (NVIDIA/Groq/OpenRouter/Gemini) ya tiene 4 proveedores
independientes sin tarjeta — no hay urgencia de agregar un 5to salvo que se
repita un incidente de caída simultánea como el de Luganense (2026-08-24).
