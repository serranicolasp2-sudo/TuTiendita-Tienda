# Tarea 7 para Antigravity: color del marco, webs sin fechas, fotos de los cuadros y muestra nueva

Todo lo hizo y probó Claude. **No modifiques nada: solo subilo y verificá.** Si ya habías subido una versión anterior de esta tarea, volvé a subir todo: estos archivos la reemplazan.

## A. Backend (el cuadro enmarcado ahora pide el color del marco: Madera o Negro)
```bash
# Copiá RegalosIA/tienda/app/ y RegalosIA/tienda/tests/ a /srv/tutienditaia/app/ (pisando lo anterior)
sudo chown -R tienda:tienda /srv/tutienditaia/app
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests
#   Esperado con los precios de prueba de $500: "4 failed, 15 passed"
#   (las 4 de siempre: test_entrega, test_conciliacion_encuentra_pago_sin_webhook,
#    test_revision_foto_un_cambio_y_aprobacion, test_cancion_tiene_cinco_cambios). Cualquier otra falla: frená y anotala.
sudo systemctl restart tutienditaia && sudo systemctl is-active tutienditaia
```

## B. Webs (pisando lo que haya)
- `web/restauraciondefotos/index.html` y `index-base.html` → `/var/www/html/public/tutienditaia/restauraciondefotos/`
- `web/restauraciondefotos/img/muestra-despues.jpg`, `cuadro-ecocuero.webp`, `cuadro-madera.webp` y `cuadro-negro.webp` → `/var/www/html/public/tutienditaia/restauraciondefotos/img/`
- `web/tucancion/index.html` → `/var/www/html/public/tutienditaia/tucancion/`

Cambios:
- Fotos: desplegable de color (A color, Mantener colores de época, En blanco y negro); galería con las fotos de los cuadros; elección del color del marco en el cuadro enmarcado; nueva muestra del antes y después.
- Las dos webs: el aviso de arriba y la pregunta "¿Llega para el Día de la Madre?" ya no tienen fechas.

## C. Verificación
```bash
B=https://campuscfp401avellaneda.com.ar/tutienditaia
curl -s $B/api/catalogo?marca=rf | grep -o '"marcos":\[[^]]*\]' | sort -u        # incluye ["Madera","Negro"]
curl -s $B/restauraciondefotos/ | grep -c 'rf-seccion-marco\|rf-galeria'         # 3 o más
curl -s $B/restauraciondefotos/ $B/tucancion/ | grep -cE '1[0-9]/10|9/10'         # 0
for f in cuadro-ecocuero.webp cuadro-madera.webp cuadro-negro.webp muestra-despues.jpg; do curl -s -o /dev/null -w "$f %{http_code} %{content_type}\n" $B/restauraciondefotos/img/$f; done   # 200
```
Si los `.webp` no salen como `image/webp`, agregá `image/webp webp;` en los mime types de Nginx (no toques nada más).

Anotá "Tarea 7 hecha" y las salidas al final de `tienda/docs/ENTREGA-ANTIGRAVITY.md`. No toques el `.env`. No hagas pedidos de prueba.
