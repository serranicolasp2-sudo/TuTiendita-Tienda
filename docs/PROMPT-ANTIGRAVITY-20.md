# Tarea 20 para Antigravity: activar el píxel de Meta (y verificar los dominios)

**APROBADA por el usuario (15/10): hacela cuando el usuario te pase el ID del píxel.** Es lo que falta de la tarea 18 (D-56). Lo de siempre: no toques `.env`, las llaves ni la contraseña de root; nada de pedidos de prueba con plata ni mails a clientes reales; lo que anotás como verificado lo miraste de verdad. Respetá la regla 10 de `redes/AGENTS.md` (una propuesta no se ejecuta sin aprobación).

## A. Cargar el ID del píxel

El usuario te pasa un número de 15 o 16 cifras (el ID del píxel, que Meta ahora llama "conjunto de datos").

1. En `tienda/web/tienda.js`, donde hoy dice `var pixelId = window.META_PIXEL_ID;`, dejá el ID como valor por defecto:
   ```js
   var pixelId = window.META_PIXEL_ID || "<ID>";
   ```
   Así lo toman todas las páginas que cargan `tienda.js` (las dos webs en sus dominios, las páginas de gracias y el portal) sin tocar cada HTML.
2. Subí `tienda.js` a donde lo sirven los dos dominios (`/tutienditaia/tienda.js`).
3. Verificá en vivo, **sin hacer pedidos**: abrí https://tucancion.com.ar/?utm_source=prueba y https://restauraciondefotos.com.ar/ con un navegador y mirá en la red que salgan pedidos a `https://www.facebook.com/tr/?id=<ID>&ev=PageView` y `ev=ViewContent`. Sin errores de JavaScript. El formulario en el celular sigue andando (`produccion/pruebas/probar_pasos_movil.py https://tucancion.com.ar <carpeta>`; ojo, ese script hoy arma las rutas con `/tutienditaia/...`: si con los dominios nuevos no sirve, anotalo).
4. `Purchase` no se prueba con un pago real: alcanza con revisar que el código no cambió desde la revisión de Claude del 14/10.

## B. Verificar los dominios en Meta (cuando el usuario te pase los registros)

En la configuración del negocio de Meta, el usuario agrega `tucancion.com.ar` y `restauraciondefotos.com.ar` y elige verificar por **registro TXT de DNS**. Meta le da un valor por dominio (`facebook-domain-verification=...`). Cargalos en Cloudflare como registro TXT en `@` de cada dominio. No toques los registros A ni CNAME.

## Al terminar

- En `tienda/docs/ENTREGA-ANTIGRAVITY.md`, una sección "Tarea 20" (qué cambiaste, qué viste en la red, dudas).
- Una entrada en `redes/BITACORA.md` (firma `Antigravity`) que diga si el píxel ya manda eventos desde los dos dominios.
