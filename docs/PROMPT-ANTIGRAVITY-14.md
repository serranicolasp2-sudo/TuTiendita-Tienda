# Tarea 14 para Antigravity: cuadro enmarcado 30x40 + webs ("Qué recibís" / "Qué incluye" compactos, galería ordenada)

Lo hizo y probó Claude. **No modifiques nada: solo subilo y verificá.** No toques `.env`, `DATOS_DIR` ni las llaves.

Qué cambia:
- **Producto nuevo `rf-cuadro-enmarcado-30x40`** (D-50): marco color madera o negro, de urbancraft (`https://meli.la/1fQNtPf` y `https://meli.la/1UFxNbZ`, $23.000 cada uno el 14/10, envío gratis con la cuenta del usuario). Ganancia neta de $5.000 como el 20x30; el precio lo calcula el vigilante con la comisión real de MP: $29.900 hoy.
- **Webs:** "Qué recibís" (Tu Canción) y "Qué incluye" (fotos) pasan a una fila de 5 ítems iguales, la mitad de alto, y carrusel en el celular. En fotos, la galería queda en el orden de las opciones ("Cuadro enmarcado (marco color madera)", "Cuadro enmarcado (marco negro)", "Ecocuero en bastidor (20x30 o 40x30)") y se suma la tarjeta del enmarcado 30x40.

**El orden importa: primero el servidor, después las páginas.** Si la página llega antes, ofrece un producto que el servidor todavía no conoce.

## A. Servidor
```bash
# Copiá RegalosIA/tienda/app/ (cambian catalogo.py y proveedores.json) y RegalosIA/tienda/tests/ a /srv/tutienditaia/app/
sudo chown -R tienda:tienda /srv/tutienditaia/app
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests
#   Esperado: "4 failed, 26 passed" (las 4 de siempre, por los precios de prueba de $500). Otra falla: frená y anotala.
sudo systemctl restart tutienditaia && sudo systemctl is-active tutienditaia
T=<TIENDA_ADMIN_TOKEN del .env; no lo pegues en ningún archivo ni en la entrega>
L=http://127.0.0.1:8091
curl -s -X POST -H "Authorization: Bearer $T" "$L/admin/vigilante" | python3 -m json.tool | grep -A6 '"precios"'
curl -s "$L/catalogo?marca=rf" | python3 -c "import json,sys; print([(p['id'], p['precio'], p['marcos']) for p in json.load(sys.stdin) if 'cuadro' in p['id']])"
```
Esperado: `rf-cuadro-enmarcado-30x40` en **$29.900** con marcos `["Madera", "Negro"]`; los demás cuadros como estaban ($24.900, $34.900, $44.900). Si el formato de `/catalogo` es distinto, mostrá la salida tal cual. No debe llegar ningún aviso de envío de las publicaciones nuevas.

## B. Páginas (copia exacta, pisando lo anterior; no subas `img/` ni `audio/`)
- `RegalosIA/web/tucancion/index.html` e `index-base.html` → `/var/www/html/public/tutienditaia/tucancion/`
- `RegalosIA/web/restauraciondefotos/index.html` e `index-base.html` → `/var/www/html/public/tutienditaia/restauraciondefotos/`

```bash
B=https://campuscfp401avellaneda.com.ar/tutienditaia
curl -s $B/tucancion/ | grep -c 'm-slides m-slides--tarjetas'            # 1
curl -s $B/restauraciondefotos/ | grep -c 'm-slides m-slides--tarjetas'  # 1
curl -s $B/tucancion/ | grep -c 'id="por-que"'                           # 1 (sigue la sección de la tarea 10)
curl -s $B/restauraciondefotos/ | grep -c 'Cuadro enmarcado (marco color madera)'   # 1
curl -s $B/restauraciondefotos/ | grep -c 'rf-cuadro-enmarcado-30x40'    # 2 (tarjeta y configuración del formulario)
```

## C. Entrega
Al final de `tienda/docs/ENTREGA-ANTIGRAVITY.md`: "Tarea 14 hecha" con la salida de `pytest`, de los `curl` (sin el token) y los precios que quedaron. No hagas pedidos de prueba.
