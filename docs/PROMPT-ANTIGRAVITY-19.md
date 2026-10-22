# Tarea 19 para Antigravity: subir los arreglos de la revisión de Claude de las tareas 17, anexo y 18

Lo hizo y probó Claude (14/10). **No modifiques nada: subí y verificá.** No toques `.env` ni las llaves. Nada de pedidos de prueba ni mails a clientes.

Qué cambia:
- **Recordatorios** (`app/main.py`, `revisar_recordatorios_fechas`):
  - solo para pedidos cobrados;
  - sale cuando faltan entre 1 y 15 días (antes era justo el día 15), una vez por cada vez que llega la fecha;
  - si el mail falla, no se marca como enviado y se reintenta;
  - sale a partir de las 10 (hora de Argentina);
  - no sale si la compra fue menos de 30 días antes de la fecha;
  - el HTML del mail va escapado.
  - `/admin/fechas` cuenta solo pedidos cobrados y muestra las próximas fechas comerciales.
- **Precios a mano:** el cambio de un cuadro a precio fijo queda bajo el candado del vigilante (`main.py` y `vigilante.fijar_modo`).
- **Píxel:** `GET /pedidos/{pid}/estado` devuelve `precio`. En `tienda/web/tienda.js`, la compra se reporta una sola vez por pedido (`eventID`).
- **Centralita:** los links directos `#precios` y `#fechas` andan (es local, no se sube).

## Subida
1. `RegalosIA/tienda/app/` y `RegalosIA/tienda/tests/` → `/srv/tutienditaia/app/app/` y `/srv/tutienditaia/app/tests/`. `pytest`: **40 passed**. `systemctl restart tutienditaia`.
2. `RegalosIA/tienda/web/tienda.js` → `/var/www/html/public/tutienditaia/tienda.js`.
3. Verificá: `curl -s $B/api/pedidos/RF-0010/estado` trae `"precio"`; `curl -s $B/tienda.js | grep -c compra-` ≥ 1.

Anotá "Tarea 19 hecha" al final de `tienda/docs/ENTREGA-ANTIGRAVITY.md`.
