# Tarea 6 para Antigravity: retención (tarea 5) + webs con precios de prueba y botones Lado A / Lado B

Todo lo hizo y probó Claude. **No modifiques nada: solo subilo y verificá.** Si la tarea 5 ya la hiciste, saltá la parte A.

## A. Backend (retención de 30 días)
```bash
# Copiá RegalosIA/tienda/app/ y RegalosIA/tienda/tests/ a /srv/tutienditaia/app/ (pisando lo anterior)
sudo chown -R tienda:tienda /srv/tutienditaia/app
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests
#   Esperado con los precios de prueba de $500: "4 failed, 14 passed"
#   (test_entrega, test_conciliacion_encuentra_pago_sin_webhook, test_revision_foto_un_cambio_y_aprobacion,
#    test_cancion_tiene_cinco_cambios simulan pagos a precio real). Cualquier otra falla: frená y anotala.
sudo systemctl restart tutienditaia && sudo systemctl is-active tutienditaia
```

## B. Webs
Subí estos archivos, pisando los del servidor:
- `web/movil.js` → `/var/www/html/public/tutienditaia/movil.js`
- `web/restauraciondefotos/index.html` y `index-base.html` → `/var/www/html/public/tutienditaia/restauraciondefotos/`
- `web/tucancion/index.html` y `index-base.html` → `/var/www/html/public/tutienditaia/tucancion/`

Cambios:
- Todos los precios visibles de 1 foto y 1 canción dicen $500, igual que el catálogo de prueba.
- En el menú de fotos aparece "Lado A: canciones" y antes de Condiciones, la franja azul "Que además suene".
- En el menú de canciones aparece "Lado B: fotos" y antes de Condiciones, la franja amarilla "Y esa foto de siempre, como nueva".

## C. Verificación
```bash
curl -s https://campuscfp401avellaneda.com.ar/tutienditaia/api/salud
curl -s https://campuscfp401avellaneda.com.ar/tutienditaia/restauraciondefotos/ | grep -c "Que además suene"   # 1
curl -s https://campuscfp401avellaneda.com.ar/tutienditaia/tucancion/ | grep -c "como nueva"                # 1 o más
```
Anotá "Tarea 6 hecha" y las salidas al final de `tienda/docs/ENTREGA-ANTIGRAVITY.md`. No toques el `.env`. No hagas pedidos de prueba.
