# Plan: header `X-Router-No-Fallback`

## Por qué surgió

En la conversación del 2026-07-04, Pulpo reportó que nodos **router/clasificadores** (p. ej. detectar si un pedido es de Villa Lugano) producían outputs distintos para el mismo input exacto con `temperature=0`.

La causa raíz: `best:instruction + cloud-first` construye una cadena de 7+ modelos. Si el proveedor top falla (rate limit, 503 transitorio), el router cae silenciosamente al siguiente — que es un modelo distinto. `temperature=0` solo controla el sampling dentro de un modelo; no ayuda cuando la identidad del modelo varía entre llamadas.

El fix aplicado ese día fue pinear el modelo explícito (`groq/openai/gpt-oss-120b`) en los nodos clasificadores. Eso resuelve el problema inmediato pero requiere que cada consumidor (Pulpo) conozca y hardcodee el modelo.

El header `X-Router-No-Fallback` sería la alternativa del lado del router para cuando se quiera usar `best:<category>` con garantía de no-switch.

## Comportamiento propuesto

```
X-Router-No-Fallback: true
```

- El router resuelve la cadena normalmente (respetando `best:<category>` y la estrategia).
- Solo intenta `chain[0]`.
- Si falla (HTTP error, excepción, o contenido vacío) → responde **502** inmediatamente, sin intentar el siguiente modelo.
- Sin este header → comportamiento actual (cascada completa).

## Cuándo usarlo

- Nodos clasificadores de intención donde la consistencia importa más que la disponibilidad.
- Cualquier caso donde un "respuesta de un modelo distinto" sea peor que un error explícito.
- **No** usar para nodos generativos donde la disponibilidad importa.

## Implementación (estimado: ~15 min)

**`router/server.py`:**

```python
# En _dispatch_chain, agregar parámetro:
async def _dispatch_chain(..., no_fallback: bool = False) -> JSONResponse:
    for i, (provider, model_id) in enumerate(chain):
        try:
            result = await dispatcher.call(...)
        except ...:
            if no_fallback:
                raise HTTPException(502, f"Provider {provider}/{model_id} failed and X-Router-No-Fallback is set")
            errors.append(...)
            continue

        if not _extract_content(result):
            if no_fallback:
                raise HTTPException(502, {...})
            errors.append(...)
            continue

        ...
        return JSONResponse(result)

# En cada endpoint, leer el header:
no_fallback = request.headers.get("x-router-no-fallback", "").lower() == "true"
...
return await _dispatch_chain(..., no_fallback=no_fallback)
```

**Tests:** agregar casos en `tests/test_dispatch_chain.py` para el path `no_fallback=True`.

## Notas

- El fix del 2026-07-06 (cascada en contenido vacío) aplica tanto con como sin este header — son ortogonales.
- Si se implementa, documentar en el módulo docstring de `server.py` junto a los otros headers.
