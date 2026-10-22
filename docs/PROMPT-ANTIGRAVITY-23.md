# Tarea 23 · Vigilante sin avisos falsos de envío y webs sin Día de la Madre

De: Claude. Lunes 19/10/2026.

> Para el usuario: pasale a Antigravity **"Leé tienda/docs/PROMPT-ANTIGRAVITY-23.md y hacelo."**

## Qué pasó

Hoy a las 07:56 llegó por ntfy el aviso "🚚 Enmarcado color madera 20x30: no dice «Llega gratis mañana». Ahora dice: «sin datos de envío»". El usuario revisó: las publicaciones de los proveedores siguen diciendo "Llega gratis mañana".

En esa lectura, ML mandó la tarjeta del producto **sin el componente de envío**. El vigilante lo tomó como un cambio. En las lecturas siguientes volvió a estar bien: la de las 16:30 dice "Llega mañana" en los cuatro enmarcados.

## Qué cambió (ya hecho y probado por Claude)

`tienda/app/vigilante.py`:
- `leer()` marca `sin_envio` cuando la tarjeta no trae el texto de envío.
- `_leer_publicacion()` cuenta esas lecturas seguidas por publicación (`estado["sin_envio"]`). Avisa recién cuando son `LECTURAS_SIN_ENVIO = 3` revisiones seguidas, o sea una hora. El aviso nuevo dice "ML no muestra el envío".
- Cuando el dato vuelve, la cuenta se reinicia.
- Un cambio **real** de envío (por ejemplo "Llega el jueves") sigue avisando al instante, igual que antes.

Hay una prueba nueva: `test_vigilante_no_avisa_por_una_lectura_sin_envio`. En total pasan **46 pruebas**.

## Lo que tenés que hacer

1. **Si la tarea 22 todavía no está desplegada, hacela primero.** El `app/` del repo ya incluye el código de la 22 y el de esta.
2. Compará `/srv/tutienditaia/app/app/vigilante.py` con el del repo anterior a este cambio. Si el del servidor tiene cambios que no están en el repo, **pará y avisá** en `redes/BITACORA.md` ("Para: Claude").
3. Copiá `RegalosIA/tienda/app/vigilante.py` y `RegalosIA/tienda/tests/test_tienda.py` al servidor, como dice `deploy/INSTALAR.md`.
4. Corré las pruebas: `sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests`. **Tienen que pasar 46.**
5. Reiniciá el servicio `tutienditaia` y corré el vigilante a mano (`POST /admin/vigilante`). Revisá que en `GET /admin/proveedores` las seis publicaciones tengan `ultima_lectura` con fecha de ahora y sin error.
6. Anotá lo hecho en `redes/BITACORA.md`, firmado.

## Parte 2 · Las webs vuelven a la versión base (sin Día de la Madre)

El 19/10 las dos webs en el aire seguían con la campaña: encabezado "Día de la Madre: …", título "Este Día de la Madre, devolvele esa foto", dedicatoria "Para mamá" y la pregunta "¿Llega para el Día de la Madre?". Según el plan, después del 18/10 `index.html` se reemplaza por `index-base.html`.

Claude ya lo hizo en el repo:
- `web/{tucancion,restauraciondefotos}/index.html` ahora es la base (sin fechas);
- la versión de campaña quedó guardada como `index-dia-de-la-madre-2026.html`, que **no se sube**.

El 19/10, lo que estaba en el aire era idéntico al `index.html` de campaña del repo.

1. Compará los `index.html` del servidor (`/var/www/html/public/tutienditaia/{tucancion,restauraciondefotos}/index.html`) con `web/*/index-dia-de-la-madre-2026.html`. Si hay diferencias, **pará y avisá** en la bitácora.
2. Subí `web/tucancion/index.html` y `web/restauraciondefotos/index.html` a su lugar. Solo esos dos archivos.
3. Revisá en el navegador https://tucancion.com.ar/ y https://restauraciondefotos.com.ar/ (celular y escritorio): no tiene que aparecer "Día de la Madre" ni "mamá" en la dedicatoria, y los precios se tienen que seguir pintando en vivo.

No toques nada más: precios, `.env` ni `proveedores.json`.
