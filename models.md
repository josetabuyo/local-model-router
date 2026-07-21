# Local Models — Inventario

Máquina: MacBook (darwin arm64) · Actualizado: 2026-06-11

---

## Runtime instalado

| Tool | Versión | Ruta | Estado |
|------|---------|------|--------|
| [Ollama](https://ollama.com) | vía Homebrew | `/opt/homebrew/bin/ollama` | ✅ corriendo (puerto 11434) |

Ollama levanta automáticamente un servidor OpenAI-compatible en `http://localhost:11434`.

---

## Modelos instalados

### gemma4:e4b — Gemma 4 8B (Google)

| Campo | Valor |
|-------|-------|
| Familia | Gemma 4 |
| Parámetros | 8B |
| Cuantización | Q4_K_M |
| Tamaño en disco | ~9.6 GB (`~/.ollama/models/`) |
| Contexto | 131 072 tokens |
| Multimodal | visión + audio + tools + thinking |
| Licencia | Apache 2.0 |
| Instalado | 2026-04-26 |

**Capacidades probadas:** completion, tool use, thinking mode.

---

## Cómo usar el modelo

### Desde la terminal

```bash
ollama run gemma4:e4b
```

### API REST (OpenAI-compatible)

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma4:e4b",
    "messages": [{"role": "user", "content": "Hola"}]
  }'
```

### Desde Python (LangChain — patrón usado en Pulpo)

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="gemma4:e4b",
    base_url="http://localhost:11434/v1",
    api_key="ollama",       # valor dummy, Ollama no valida
    temperature=0.3,
)
result = llm.invoke([{"role": "user", "content": "Hola"}])
print(result.content)
```

### Desde Python (SDK nativo de Ollama)

```python
import ollama

response = ollama.chat(model="gemma4:e4b", messages=[
    {"role": "user", "content": "Hola"}
])
print(response["message"]["content"])
```

---

## Integración con Pulpo

En los nodos LLM de Pulpo se usa el prefijo `local:` para invocar modelos locales:

- Model ID en Pulpo: `local:gemma4:e4b`
- Env var de override: `OLLAMA_BASE_URL` (default: `http://localhost:11434/v1`)
- Archivo de integración: `pulpo/_/backend/graphs/nodes/llm.py`

---

## Comandos útiles de Ollama

```bash
ollama list                    # modelos instalados
ollama show gemma4:e4b         # detalles del modelo
ollama pull <modelo>           # descargar nuevo modelo
ollama rm <modelo>             # eliminar modelo
ollama serve                   # iniciar servidor manualmente (si no está corriendo)
ollama ps                      # ver modelos cargados en memoria
```

---

## Modelos a explorar (candidatos)

| Modelo | Tamaño | Notas |
|--------|--------|-------|
| `gemma4:27b` | ~17 GB | Versión más grande de Gemma 4, mejor calidad |
| `gemma4:4b` | ~3 GB | Más liviano, respuestas más rápidas |
| `llama3.2:3b` | ~2 GB | Llama 3.2 3B, muy rápido |
| `llama3.1:8b` | ~5 GB | Meta Llama 3.1 8B |
| `qwen2.5:7b` | ~5 GB | Qwen 2.5, muy bueno en código |
| `mistral:7b` | ~4 GB | Mistral 7B |
| `phi4:14b` | ~9 GB | Microsoft Phi-4, excelente reasoning |
| `deepseek-r1:8b` | ~5 GB | DeepSeek R1 con thinking |
| `nomic-embed-text` | ~274 MB | Embeddings locales |

> Para comparar benchmarks: https://ollama.com/library

---

## Próximos pasos

- [ ] Instalar agente local en esta carpeta (local-agent-society)
- [ ] Evaluar si vale la pena bajar `gemma4:27b` para tareas de mayor calidad
- [ ] Probar `nomic-embed-text` para embeddings en proyectos locales
- [ ] Configurar `OLLAMA_NUM_GPU_LAYERS` para optimizar uso de GPU (Apple Silicon)
