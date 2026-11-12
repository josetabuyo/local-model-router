# Proposal: Gemini Decision 1 as a free cloud backend for /v1/systemone

Status: PROPOSAL (model-scout 2026-11-12). Not wired. It changes the decision
cascade, so the user decides.

## What it is

Google launched the **Gemini Decisions API** with the model `gemini-decision-1`
on 2026-11-11. It scores options in a single forward pass instead of generating
text. It uses the same question vocabulary as TypeSafe Jev's System One: `noul`,
`choice` (2-255 options) and `score` (2-255 levels).

- Endpoint: `POST https://generativelanguage.googleapis.com/v1beta/decisions`,
  header `x-goog-api-key`.
- Body: `{"model":"gemini-decision-1","input":<string|Content[]>,"questions":{...}}`.
  The only differences from our body are `input` instead of `state` and a
  `model` field.
- Response: `{"answers":{q:{type, choice|score|noul, probabilities, confidence, legend}}, "usage":{...}}`.
  This is already our `answers` shape. `usage` has `total_input_tokens` and
  `total_output_tokens` (always 0) instead of `input_tokens`/`output_tokens`.
- Input: multimodal (text/image/audio/video/PDF), 262,144-token context, up to
  1,000 questions per request.
- Free tier on the **existing GEMINI_API_KEY** (no new key, no card): 200 RPM,
  50k TPM, 10,000 RPD per project. Paid tier: $0.10 per 1M input tokens, 0 for output.
- Privacy: free-tier Gemini API traffic may be used by Google to improve
  products. The same caveat already applies to our Gemini chat slots.

## Live evidence (2026-11-12, own probes)

- `plans/jev-example.json`: 200 in 1.3 s. department=technical (0.98),
  frustration score 1.26 (level 1, 0.64), is_urgent 0.99.
- `plans/systemone-cases.json` (12 cases × 3 questions): department 12/12,
  frustration 11/12, is_urgent 12/12, so 35/36 = 97%. p50 1.26 s, max 1.44 s.
  The one miss: a demo-tomorrow message labelled calm (0) got 1.
  - Reference: d3:4b-nvfp4 local scored 97% at 1.41 s on the same file (10-31).
- `plans/systemone-cases-luganense.json` (13 cases, `ruta`): 13/13, p50 1.26 s.
- Today's router baseline: local `ollama-chat/qwen3.5:4b` 200 in 35 s (cold).

## Benchmarks (vendor + press, not independent)

- Google's blog says it "leads across the suite, with the lowest calibration
  error", but the figures are only in images.
- Press coverage of Google's tables says TypeSafe Jev 1.14 beats it by 0.6 pp on
  Mind2Web Multimodal and by 2.1 pp on When2Call.
- There is no LMArena or Artificial Analysis entry for decision models.

## Integration steps (if approved)

1. `router/systemone.py`: add provider `gemini`, with
   `DEFAULT_MODELS["gemini"] = "gemini-decision-1"` and
   `GEMINI_DECISIONS_URL = ".../v1beta/decisions"`.
   - In `call_jev`, a `gemini` branch posts
     `{"model", "input": state, "questions"}` with `x-goog-api-key` and maps
     `usage.total_input_tokens` to `input_tokens`, with `output_tokens: 0`.
   - Enable it only if `GEMINI_API_KEY` is set. Set `TIMEOUTS["gemini"] = 15`.
2. Order: probably `laya,ollama-chat,gemini,typesafe,openrouter`, as the first
   cloud fallback because it is free and about 1.3 s.
   - Alternative, if latency matters more than locality:
     `gemini,ollama-chat,...`, since local qwen3.5:4b answers in 8-35 s.
3. Map HTTP 400 safety errors (`error.code` in
   safety/prohibited_content/blocklist/...) to "try next provider", not 5xx.
4. Add a `gemini` column to `scripts/jev_compare.py`.
5. Tests: one mocked `call_jev("gemini", ...)` test for the body/usage mapping.

## Sources

- blog.google/innovation-and-ai/technology/developers-tools/gemini-decisions-api/ (2026-11-11)
- aistudio.google.com/docs/decisions-api, aistudio.google.com/docs/models/gemini-decision-1,
  aistudio.google.com/docs/rate-limits (read 2026-11-12)
- siliconangle.com/2026/11/11/google-enters-the-decision-model-market-with-gemini-decisions-api/
- marktechpost.com/2026/11/11/google-gemini-decisions-api-gemini-decision-1/
  (Jev 1.14 comparison as quoted in search results; page returned 403 to fetch)
