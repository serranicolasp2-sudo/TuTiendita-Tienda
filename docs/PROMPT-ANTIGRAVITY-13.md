# Tarea 13 para Antigravity: comisión real de Mercado Pago en los precios (subir y verificar)

Lo programó y probó Claude (decisión D-49). **No modifiques nada: subilo y verificá.** No toques `.env`, `DATOS_DIR` ni las llaves.

Qué cambia: el vigilante ya no calcula el precio de los cuadros con un 8 % fijo de Mercado Pago (`NETO_MP = 0,92`). Ahora usa lo que MP cobró de verdad en las ventas de la tienda, leído por la API de MP (`app/pagos.py`). Si no hay cobros leídos, no cambia precios y avisa. `/admin/pagos` usa el mismo módulo, y `/admin/costos` devuelve también `comision_mp` (la que usó el vigilante).

También va en `proveedores.json`: las dos publicaciones de ecocuero quedan marcadas `gratis_con_tu_cuenta` (como las del enmarcado). La página pública, que es la que lee el servidor sin la cuenta del usuario, a veces muestra "Llega mañana" sin "gratis", y eso disparaba un aviso falso: con la cuenta del usuario (Meli+) el envío es gratis. Desde ahora en esas publicaciones solo se controla que llegue mañana.

## A. Subir
```bash
# Copiá RegalosIA/tienda/app/ (incluye el nuevo pagos.py, main.py, vigilante.py y proveedores.json) y RegalosIA/tienda/tests/
# a /srv/tutienditaia/app/ (pisando lo anterior)
sudo chown -R tienda:tienda /srv/tutienditaia/app
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests
#   Esperado con los precios de prueba de $500: "4 failed, 26 passed" (las 4 de siempre). Otra falla: frená y anotala.
sudo systemctl restart tutienditaia && sudo systemctl is-active tutienditaia
```

## B. Recalcular ahora y verificar (esto sí cambia precios en la web: es lo que pidió el usuario)
```bash
T=<TIENDA_ADMIN_TOKEN del .env; no lo pegues en ningún archivo ni en la entrega>
L=http://127.0.0.1:8091
curl -s -X POST -H "Authorization: Bearer $T" "$L/admin/vigilante" | python3 -m json.tool | grep -A4 '"precios"'
curl -s -H "Authorization: Bearer $T" "$L/admin/costos" | python3 -c "import json,sys; print(json.load(sys.stdin)['comision_mp'])"
```
Esperado (con las lecturas del 14/10):
- `comision_mp`: `porcentaje` 4.3, `pagos` 6, `fuente` "API de Mercado Pago: comisiones de tus cobros reales".
- Precios: enmarcado 20x30 **$24.900** (antes $25.900: con la comisión real alcanza un precio menor para la misma ganancia), ecocuero 20x30 $34.900 y 40x30 $44.900 (sin cambios, su costo no cambió).
- Si algún precio da distinto, anotá el costo leído de cada publicación (`"lecturas"`) y no toques nada más.
- Después de esa revisión no tiene que llegar ningún aviso "no dice Llega gratis mañana" de las publicaciones de ecocuero.

## C. Entrega
Al final de `tienda/docs/ENTREGA-ANTIGRAVITY.md`: "Tarea 13 hecha" con la salida de `pytest`, de los dos `curl` (sin el token) y los precios que quedaron.
