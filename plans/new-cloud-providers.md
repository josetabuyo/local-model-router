# Nuevos proveedores cloud de LLM gratis — propuesta (2026-08-22)

Encontrados en la auditoría diaria de `model-scout` vía búsqueda web abierta
(no en el cascade actual: NVIDIA NIM → Groq → OpenRouter). No integrados
todavía porque cada uno requiere una API key nueva del usuario — dejar como
propuesta hasta que se decida agregarlos.

## Cerebras — candidato fuerte, mismo rol que Groq

- Free tier: ~1M tokens/día, sin tarjeta de crédito.
- Igual que Groq: inferencia LPU/wafer-scale, velocidad como diferencial
  frente a NVIDIA NIM/OpenRouter.
- Encaja como un tercer proveedor "rápido" en las categorías donde Groq ya es
  slot 0 (`multilingual`, `coding`, `code_debug`) — redundancia útil si Groq
  rate-limitea (30 RPM/1000 RPD por modelo es bastante más chico que el 1M
  tok/día de Cerebras).
- Pasos de integración: agregar `benchmark/providers/cerebras_provider.py`
  (mismo patrón que `groq_provider.py`, base OpenAI-compatible), env var
  `CEREBRAS_API_KEY`, agregar a `router/dispatcher.py` y a
  `rankings/cloud.yaml` con benchmarks live verificados.

## Google Gemini API — candidato para `context` / respaldo de calidad

- Free tier: hasta 1M tokens de contexto, límites de volumen más bajos que
  Groq/Cerebras.
- No requiere tarjeta.
- Encajaría en `context` (ya hay 3 entradas NVIDIA con contexto 1M — Gemini
  sería una opción de proveedor diferente, no solo modelo diferente, lo cual
  ayuda si NVIDIA NIM tiene un mal día) y como respaldo de calidad general.
- Pasos de integración: `benchmark/providers/gemini_provider.py`, env var
  `GEMINI_API_KEY`, confirmar límites reales de RPM/RPD antes de sumarlo al
  cascade (Google no siempre publica los límites del free tier con precisión).

## No integrados (evaluados, no encajan)

- Mistral — free tier confirmado pero sin diferencial claro frente a lo que
  ya cubre NVIDIA NIM en las categorías actuales; no hay urgencia.
- Together AI, Vercel AI Gateway, Cloudflare AI Gateway, Requesty, Portkey,
  LiteLLM, Kong AI Gateway — son gateways/agregadores, no proveedores de
  modelo directo; no aportan modelos gratis nuevos, solo enrutan a los que ya
  tenemos o a proveedores pagos. Fuera de alcance de este proyecto (el router
  ya es el propio agregador).

## Siguiente paso

Si el usuario confirma agregar alguno: crear la API key, agregarla a `.env`,
y correr `model-scout` de nuevo — el skill ya sabe cómo auditar y sumar un
proveedor con benchmarks verificados en vivo.
