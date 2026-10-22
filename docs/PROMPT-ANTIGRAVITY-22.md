# Tarea 22 · Vuelta de Mercado Pago a los dominios propios, pago por transferencia, avisos, foto de regalo y formulario sin pago

De: Claude. Sábado 17/10/2026. **Urgente: hoy es el último día de pedidos para el Día de la Madre.**

> Para el usuario: pasale a Antigravity **"Leé tienda/docs/PROMPT-ANTIGRAVITY-22.md y hacelo."**

## Qué pasó

El usuario hizo una compra de prueba (RF-0011) y encontró tres problemas:
1. Al volver de Mercado Pago, pague o cancele, la página de "gracias" abre en **campuscfp401avellaneda.com.ar**, no en restauraciondefotos.com.ar ni en tucancion.com.ar.
2. Si no paga, la página dice "Estamos esperando la confirmación" y no ofrece otra salida.
3. A él no le llega ningún aviso de que alguien empezó un pedido y no lo pagó.

Después el usuario pidió además:
- un **mail con una foto de regalo a los 30 minutos sin pago**, con un link de un solo uso;
- el **mismo formulario sin pago** para quienes compran en Mercado Libre (D-61).

El código ya está hecho y probado por Claude: 45 pruebas; la página de gracias y el formulario con link de un solo uso, revisados en el celular con un servidor simulado. **Tu tarea es desplegarlo y cambiar dos líneas del `.env`.**

## Antes de empezar

1. Hacé backup de `/srv/tutienditaia/datos/tienda.db`.
2. **Compará el servidor con el repo** antes de copiar nada. Si alguno de estos archivos del servidor tiene cambios que no están en el repo local, **pará y avisá** en la bitácora (`redes/BITACORA.md`, "Para: Claude"). No pises trabajo de nadie.
   - `/srv/tutienditaia/app/app/{main,db,config,flujo}.py` contra `RegalosIA/tienda/app/` (la versión de antes de este cambio es del 14/10).
   - `tienda.js` contra `RegalosIA/tienda/web/tienda.js`. El que está en el aire coincidía el 17/10 a las 15 h con la versión anterior del repo.
   - Los dos `gracias.html` (`/var/www/html/public/tutienditaia/{restauraciondefotos,tucancion}/gracias.html`) contra `RegalosIA/web/*/gracias.html`.

## Lo que tenés que hacer

1. **Código de la API:** copiá `RegalosIA/tienda/app/` y `tienda/tests/` a `/srv/tutienditaia/app/`, como dice `deploy/INSTALAR.md`.
   - Cambian `db.py`, `config.py`, `flujo.py` y `main.py`. La base se migra sola: 6 columnas nuevas en `pedidos` y la tabla `canjes`, sin borrar nada.
   - Corré las pruebas: `sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests`. **Tienen que pasar 45.**
2. **`.env`** (`/srv/tutienditaia/.env`): agregá o cambiá estas líneas.
   ```
   URL_WEB_TC=https://tucancion.com.ar
   URL_WEB_RF=https://restauraciondefotos.com.ar
   ```
   Con eso, Mercado Pago vuelve a `https://<dominio de la marca>/gracias.html?pedido=…` y los links de revisión de los clientes también salen con el dominio de la marca (Nginx ya pasa `/revisar/` a la API).
   - `URL_PUBLICA` (el webhook) queda como está.
   - Los datos de transferencia ya tienen valor por defecto: alias `tutiendita.ia`, CBU `0000003100082867824654`. Solo agregá `TRANSFERENCIA_ALIAS` / `TRANSFERENCIA_CBU` si el usuario te pide cambiarlos.
   - Sacá retornos de carro como dice INSTALAR.md.
3. `sudo systemctl restart tutienditaia` (restart, no reload).
4. **Web:** copiá los archivos al servidor.
   - `RegalosIA/tienda/web/tienda.js` → `/var/www/html/public/tutienditaia/tienda.js`.
   - `RegalosIA/web/restauraciondefotos/gracias.html` y `RegalosIA/web/tucancion/gracias.html` a sus carpetas.
   - **Purgá la caché de Cloudflare** de `tienda.js` y de los dos `gracias.html`, en los dos dominios.

## Cómo verificar (sin comprar nada)

- `curl https://tucancion.com.ar/tutienditaia/api/catalogo` trae `"transferencia": {"alias": "tutiendita.ia", "cbu": "0000003100082867824654"}`.
- `curl https://restauraciondefotos.com.ar/tutienditaia/api/pedidos/RF-0011/estado` trae `transferencia_avisada: false`. RF-0011 es la prueba del usuario y sigue sin pagar.
- En el celular, `https://restauraciondefotos.com.ar/gracias.html?pedido=RF-0011&collection_status=null` muestra "¿No pudiste realizar la compra?" con:
  - el botón "Volver a intentar con Mercado Pago";
  - alias, CBU, monto ($4.999) y pedido;
  - "Mandar el comprobante por WhatsApp".
  - **No toques** "Mandar el comprobante": le llegaría al usuario un aviso de transferencia falso.
- `curl -I` de `https://restauraciondefotos.com.ar/gracias.html`: 200.
- En unos minutos le llega al usuario el aviso **"🛒 Pedido sin pagar RF-0011"**, y a su mail el de la **foto de regalo** con un link `https://restauraciondefotos.com.ar/?canje=…`. Es su propia prueba (RF-0011) y sirve para confirmar que los dos andan. Avisale que van a llegar.
- Ese link, abierto en el celular, muestra el formulario de 1 foto con "🎁 Tu foto de regalo…" y el botón "Pedir mi foto de regalo". **No lo envíes**: crearía un pedido real de regalo.
- `curl https://tucancion.com.ar/tutienditaia/api/canje/inventado` → 404.

## Lo que NO hacés

- Cambiar precios, el webhook, Nginx o cualquier otra cosa del `.env`.
- Mandar mails a mano a los "interesados": el servidor ya manda el de la foto de regalo solo, a los 30 minutos, uno por mail o WhatsApp, y no lo manda si hay un pago en efectivo pendiente.
- Tocar `index.html` de las webs: el formulario sin pago lo arma `tienda.js` cuando la dirección trae `?canje=`.
- Aprobar o cancelar pedidos.

## Al terminar

Una entrada en `redes/BITACORA.md`: qué copiaste, el resultado de las 45 pruebas, la salida de las verificaciones y si llegaron el aviso y el mail de regalo de RF-0011.
