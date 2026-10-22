# Tarea 8 para Antigravity: precios ajustables, retorno de la API de ML, tiempos de entrega, botones Lado A/B, marco, modos de color y muestras nuevas

Todo lo hizo y probó Claude. **No modifiques nada: solo subilo y verificá.** (Esta versión reemplaza a la anterior de la tarea 8.)

## A. Backend
Novedades: `POST /admin/precios` (con el token de admin) cambia precios sin reiniciar y los guarda en `DATOS_DIR/precios.json` (lo usa el vigilante de proveedores de la PC); `GET /ml/callback` muestra el código de autorización de Mercado Libre (no guarda nada); textos de tiempos de entrega en los mails.
```bash
# Copiá RegalosIA/tienda/app/ y RegalosIA/tienda/tests/ a /srv/tutienditaia/app/ (pisando lo anterior)
sudo chown -R tienda:tienda /srv/tutienditaia/app
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests
#   Esperado con los precios de prueba de $500: "4 failed, 17 passed" (las 4 de siempre:
#   test_entrega, test_conciliacion_encuentra_pago_sin_webhook, test_revision_foto_un_cambio_y_aprobacion,
#   test_cancion_tiene_cinco_cambios). Cualquier otra falla: frená y anotala.
sudo systemctl restart tutienditaia && sudo systemctl is-active tutienditaia
```

## B. Webs (pisando lo que haya)
Destino: `/var/www/html/public/tutienditaia/` + la misma ruta relativa.
- `web/index.html`, `web/movil.css`, `web/movil.js`
- `tienda/web/tienda.js` → `/var/www/html/public/tutienditaia/tienda.js`
- `web/restauraciondefotos/index.html`, `index-base.html`, `gracias.html`
- `web/restauraciondefotos/img/modo-color.webp`, `modo-epoca.webp`, `modo-byn.webp`
- `web/tucancion/index.html`, `index-base.html`, `gracias.html`
- `web/tucancion/audio/muestra-una-vez-mas.mp3`, `muestra-promesas-de-eternidad.mp3`, `muestra-pero-a-poquito-a-poco.mp3`
- **Borrá** `/var/www/html/public/tutienditaia/tucancion/audio/muestra-cuadra-mia.mp3`

Cambios: botón "Lado A: canciones" en azul y "Lado B: fotos" en amarillo; la elección del marco solo aparece con el cuadro enmarcado; el modo de color se elige con 3 tarjetas que explican cada opción (en fotos y en el combo); tiempos (fotos: vista previa en menos de 2 h; canción: menos de 48 h; video: hasta 72 h); 4 muestras ("Muestra 1" a "Muestra 4"); la web de fotos lee los precios del servidor; en el celular, el menú queda en dos botones, las listas largas pasan a slides con puntitos y los formularios se completan en pasos; la página de revisión del cliente tiene un botón grande para ver la vista previa.

## C. Verificación
```bash
B=https://campuscfp401avellaneda.com.ar/tutienditaia
curl -s -o /dev/null -w "precios sin token: %{http_code}\n" -X POST -H 'Content-Type: application/json' -d '{}' $B/api/admin/precios   # 401
curl -s "$B/api/ml/callback?code=TG-prueba-123" | grep -c 'TG-prueba-123'   # 1
curl -s -o /dev/null -w "notificaciones ML: %{http_code}
" -X POST -H 'Content-Type: application/json' -d '{}' $B/api/ml/notificaciones   # 200
curl -s $B/restauraciondefotos/ | grep -c 'Marco color madera'    # 2 o más
curl -s $B/restauraciondefotos/ | grep -c 'menos de 2 h'          # 3 o más
curl -s $B/restauraciondefotos/ | grep -c 'class="modo"'          # 3
curl -s $B/tucancion/ | grep -c 'Muestra [1-4]'                    # 8
curl -s $B/tucancion/ | grep -c 'cuadra-mia'                       # 0
curl -s $B/tienda.js | grep -c 'menos de 2 horas'                 # 1
curl -s $B/movil.js | grep -c 'm-pasos'                            # 1 o más
for f in tucancion/audio/muestra-una-vez-mas.mp3 tucancion/audio/muestra-promesas-de-eternidad.mp3 tucancion/audio/muestra-pero-a-poquito-a-poco.mp3 restauraciondefotos/img/modo-color.webp restauraciondefotos/img/modo-epoca.webp restauraciondefotos/img/modo-byn.webp; do curl -s -o /dev/null -w "$f %{http_code}\n" $B/$f; done   # 200
curl -s -o /dev/null -w "cuadra-mia %{http_code}\n" $B/tucancion/audio/muestra-cuadra-mia.mp3   # 404
```
Anotá "Tarea 8 hecha" y las salidas al final de `tienda/docs/ENTREGA-ANTIGRAVITY.md`. No toques el `.env`. No hagas pedidos de prueba.
