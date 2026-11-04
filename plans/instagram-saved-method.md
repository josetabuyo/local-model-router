# Cómo revisar los guardados de Instagram de José

Método usado el 2026-10-31 (inventario: `plans/instagram-saved-2026-10-31.md`).
Sirve para repetirlo cada tanto y sacar ideas de mejora para todos los proyectos.

- Perfil: **@jozbuyo** (https://www.instagram.com/jozbuyo/saved/). Lo que se revisa son
  los **posts guardados**. José los llama a veces "reminders".
- Colecciones: "All posts" tiene todo (205 al 2026-10-31). "Va" está vacía.

## 1. Sacar la lista completa (Chrome, sesión de José ya abierta)

Nunca se escribe la contraseña ni un código de verificación. Si Instagram pide login, lo hace José.

1. Pestaña nueva en `https://www.instagram.com/jozbuyo/saved/all-posts/`.
2. Desde esa pestaña se llama a la API web de Instagram con la cookie de la sesión. Es más rápido y
   completo que hacer scroll, y devuelve el caption entero:

```js
const out = []; let max_id = '';
for (let i = 0; i < 40; i++) {
  const r = await fetch('/api/v1/feed/saved/posts/' + (max_id ? '?max_id=' + encodeURIComponent(max_id) : ''),
    { headers: { 'X-IG-App-ID': '936619743392459' }, credentials: 'include' });
  if (!r.ok) { out.push({ err: r.status }); break; }
  const j = await r.json();
  for (const it of j.items || []) {
    const m = it.media;
    out.push({ code: m.code, type: m.media_type, pt: m.product_type, user: m.user?.username,
                taken: new Date(m.taken_at * 1000).toISOString().slice(0, 10), cap: m.caption?.text || '' });
  }
  if (!j.more_available) break;
  max_id = j.next_max_id;
}
window.__inv = out; out.length;
```

3. Los datos se leen de `window.__inv` en tandas, porque la herramienta corta las salidas largas, y
   se guardan en un JSON local. El link de cada post es `https://www.instagram.com/p/<code>/`; si
   `pt` es `clips`, es `/reel/<code>/`.
4. Plan B si la API falla: hacer scroll hasta el final, juntar `main a[href*="/p/"], main a[href*="/reel/"]`
   y usar el `alt` de cada imagen. Trae menos texto.

## 2. Revisar

- Por cada post, leer el caption (los reels casi siempre traen el texto de lo que dicen) y anotar qué
  afirma, con el link. Son afirmaciones del autor, **sin verificar**, hasta que alguien las pruebe.
- Clasificar por tema y por el agente al que le sirve. En 2026-10-31, unos 100 eran de tech/IA:
  modelos locales, harness, voz, robótica.
- Por cada idea útil: a qué agente va, qué tendría que probar o cambiar, y prioridad.

## 3. Distribuir

- Primero se le muestra a José la tabla post → agente → propuesta.
- **Nada se envía a los agentes sin que José lo apruebe.**
- Después, a cada agente le llega un mensaje con sus posts y la propuesta. Cada agente prueba de a
  una cosa y anota el resultado en su repo.
