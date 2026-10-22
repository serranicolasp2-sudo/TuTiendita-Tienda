# Tarea 16 para Antigravity: precios reales (se terminan los $500 de prueba) y precios en vivo en toda la web

**Hacela después de terminar la tarea 15.** Lo preparó y probó Claude. **No modifiques nada a mano: corré el script, subí y verificá.** No toques `.env` ni `DATOS_DIR`. No hagas pedidos de prueba.

Qué cambia (D-20 y D-51):
- La foto suelta (`rf-foto-1`) vuelve a **$5.000** y la canción (`tc-cancion`) a **$27.000**.
- Todos los precios escritos en las webs (encabezado, tablas, tarjetas, "por foto" de los packs, resumen del formulario, barra del celular) quedan marcados con `data-precio` y `tienda.js` los pinta con el precio del servidor. El número del HTML es solo el valor de arranque. Así la página nunca muestra algo distinto de lo que se cobra, y un cambio de precio (a mano o del vigilante) se ve en todos lados.
- Ya están cambiados por Claude: `tienda/web/tienda.js`, `web/movil.js` y `web/tucancion/index.html` e `index-base.html`. Falta lo que toca archivos de la tarea 15, que hace el script del paso 1.

## 1. Script (en la PC)
```bash
python tienda/docs/tarea16_precios.py
```
Tiene que decir "listo" (o "ya estaba aplicado") para `tienda/app/catalogo.py` y las dos páginas de fotos. **Si dice "FRENO", pará y anotalo**: no edites los archivos a mano.

## 2. Servidor (a la carpeta que usa el servicio, según el paso 0 de la tarea 15)
```bash
# Copiá RegalosIA/tienda/app/ y RegalosIA/tienda/tests/
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests
#   Esperado: TODO en verde. Las 4 fallas de siempre eran por los precios de prueba: con los reales tienen que pasar.
#   Si falla alguna, pará y anotala.
sudo systemctl restart tutienditaia && sudo systemctl is-active tutienditaia
```

## 3. Archivos de las webs (copia exacta, pisando lo anterior; no subas `img/` ni `audio/`)
- `RegalosIA/tienda/web/tienda.js` → `/var/www/html/public/tutienditaia/tienda.js`
- `RegalosIA/web/movil.js` → `/var/www/html/public/tutienditaia/movil.js`
- `RegalosIA/web/tucancion/index.html` e `index-base.html` → `.../tutienditaia/tucancion/`
- `RegalosIA/web/restauraciondefotos/index.html` e `index-base.html` → `.../tutienditaia/restauraciondefotos/`

## 4. Precios en el servidor (recién después del paso 3)
```bash
T=<TIENDA_ADMIN_TOKEN del .env; no lo pegues en ningún archivo ni en la entrega>
curl -s -X POST -H "Authorization: Bearer $T" -H "Content-Type: application/json" \
     -d '{"rf-foto-1": 5000, "tc-cancion": 27000}' http://127.0.0.1:8091/admin/precios
curl -s "http://127.0.0.1:8091/catalogo" | python3 -c "import json,sys; print({p['id']: p['precio'] for p in json.load(sys.stdin)['productos']})"
```
Esperado: `rf-foto-1` 5000, `tc-cancion` 27000, `tc-combo` 59900, packs 15000/25000/39900, cuadros como estaban (24900, 29900, 34900, 44900).

## 5. Verificación de las webs
```bash
B=https://campuscfp401avellaneda.com.ar/tutienditaia
curl -s $B/tienda.js | grep -c "pintarPrecios"                         # 3 o más
curl -s $B/tucancion/ | grep -c 'data-precio="tc-cancion"'             # 4
curl -s $B/restauraciondefotos/ | grep -c 'data-precio='               # 8
curl -s $B/tucancion/ $B/restauraciondefotos/ $B/movil.js | grep -c '\$500'   # 0
```
Y con Chrome headless (o a mano), las dos webs: el encabezado de Tu Canción dice **$27.000** y el de fotos **$5.000 por foto**. Mirá las capturas antes de anotarlas.

## 6. Entrega
Al final de `tienda/docs/ENTREGA-ANTIGRAVITY.md`: "Tarea 16 hecha" con la salida del script, `pytest`, los `curl` (sin el token) y lo que viste en las capturas.
