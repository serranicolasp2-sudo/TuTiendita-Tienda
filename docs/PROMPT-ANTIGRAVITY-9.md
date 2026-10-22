# Tarea 9 para Antigravity: vigilante de proveedores en el servidor, "Marco color madera" y notificaciones de ML

Todo lo hizo y probó Claude. **No modifiques nada: solo subilo y verificá.** No toques `DATOS_DIR` (ahí está `precios.json`, que ajusta el vigilante) ni el `.env`. (Esta versión reemplaza a la anterior de la tarea 9.)

Novedades del backend:
- `app/vigilante.py` + `app/proveedores.json`: cada 30 minutos, dentro del ciclo de la tienda, lee los 4 links meli.la de los cuadros de proveedores (precio y "Llega gratis mañana"), ajusta solo el precio de venta y avisa por ntfy. Antes corría en la PC; ahora no depende de que esté prendida.
- `POST /admin/vigilante` (con el token de admin; `?prueba=true` solo lee) para correrlo a mano.
- `POST /ml/notificaciones` (responde 200, no guarda nada) y el texto "marco color madera" en el catálogo.

## A. Backend
```bash
# Copiá RegalosIA/tienda/app/ (incluye vigilante.py y proveedores.json) y RegalosIA/tienda/tests/ a /srv/tutienditaia/app/ (pisando lo anterior)
sudo chown -R tienda:tienda /srv/tutienditaia/app
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests
#   Esperado con los precios de prueba de $500: "4 failed, 18 passed" (las 4 de siempre). Otra falla: frená y anotala.
sudo systemctl restart tutienditaia && sudo systemctl is-active tutienditaia
```

## B. Webs (pisando lo que haya)
- `web/restauraciondefotos/index.html` e `index-base.html` → `/var/www/html/public/tutienditaia/restauraciondefotos/`
- `web/index.html` → `/var/www/html/public/tutienditaia/index.html` (el "desde" de los cuadros ahora lo lee del servidor)

## C. Verificación (no copies el token en ningún archivo ni en la salida)
```bash
B=https://campuscfp401avellaneda.com.ar/tutienditaia
TOKEN=$(sudo grep '^TIENDA_ADMIN_TOKEN=' /srv/tutienditaia/.env | cut -d= -f2- | tr -d '\r"')
curl -s -X POST -H "Authorization: Bearer $TOKEN" "$B/api/admin/vigilante?prueba=true" | python3 -m json.tool | grep -E '"nombre"|"precio"|"envio"|"error"'
#   Esperado: las 4 publicaciones con precio y envío, y "error": "" en todas
unset TOKEN
curl -s -o /dev/null -w "notificaciones ML: %{http_code}\n" -X POST -H 'Content-Type: application/json' -d '{}' $B/api/ml/notificaciones   # 200
curl -s "$B/api/catalogo?marca=rf" | grep -c 'marco color madera'   # 1
curl -s $B/restauraciondefotos/ | grep -c 'Marco color madera'      # 3 o más
sleep 150; sudo journalctl -u tutienditaia --since "5 min ago" | grep -E "Ecocuero|Enmarcado|vigilante" | tail -6   # la primera vuelta automática
```
Anotá "Tarea 9 hecha" y las salidas al final de `tienda/docs/ENTREGA-ANTIGRAVITY.md`. No hagas pedidos de prueba.
