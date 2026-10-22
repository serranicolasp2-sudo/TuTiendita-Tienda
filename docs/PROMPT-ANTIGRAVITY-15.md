# Tarea 15 para Antigravity: Centralita, fase 3 (proveedores, seguimiento del cuadro, clientes)

Programás vos; Claude revisa al final. **Leé antes:** `centralita/PLAN.md` (reglas que no se negocian), `centralita/ENTREGA.md` §6 y §8 (lo que se corrigió en las fases 1 y 2: no repitas esos errores), el prototipo `centralita/prototipo.html` (pantalla Proveedores) y `DECISIONES.md` D-47 a D-50.

**Al terminar, frená.** Dejá en `centralita/ENTREGA.md` una sección "Fase 3" (qué hiciste, salida de las pruebas, qué verificaste con datos reales, dudas). No toques `.env`, `DATOS_DIR` (salvo lo que se pide en el paso 0, que es fuera de él), las llaves ni la contraseña de root. Nada de pedidos de prueba ni mails a clientes reales.

Recordatorios de las fases anteriores:
- El servicio local es `centralita/servicio.py` y lo arranca `centralita/arrancar.py` (con pythonw no hay consola). No crees `app.py` en `centralita/`.
- Nada que llegue del navegador se usa como ruta de archivo. Todo lo de la interfaz pasa por `api()` con `X-Centralita`.
- Solo datos reales; si falta uno, "sin dato". Lo que anotás como verificado, lo miraste de verdad.

---

## 0. Primero: copias duplicadas en el servidor
En las tareas 13 y 14 anotaste que copiaste los archivos en `/srv/tutienditaia/app/app/` **y** sueltos en `/srv/tutienditaia/app/` ("raíz"). Si una subida futura actualiza solo una copia, puede quedar corriendo código viejo sin que se note.
1. Averiguá cuál usa el servicio: `systemctl cat tutienditaia` (`WorkingDirectory`, `ExecStart`) y `sudo -u tienda /srv/tutienditaia/venv/bin/python -c "import app.main as m; print(m.__file__)"` desde ese `WorkingDirectory`.
2. Las copias que **no** usa: no las borres. Movelas a `/srv/tutienditaia/respaldo-duplicados-2026-10-14/` conservando la estructura.
3. Reiniciá, `curl -s http://127.0.0.1:8091/salud` y `pytest` ("4 failed, 26 passed" o más passed si sumás pruebas).
4. Anotá en `ENTREGA-ANTIGRAVITY.md` qué carpeta usa el servicio y qué moviste. **De ahora en más, subí solo a esa.**

## A. Servidor (`tienda/app/`)

### A1. Historial de precios de los proveedores (`vigilante.py`)
Hoy el estado (`proveedores-estado.json`) guarda solo el último precio de cada publicación (`est["costos"][nombre]`).
- Sumá `est["historial"][nombre]`: lista de `{"fecha": ISO, "precio": int, "fuente": "vigilante" | "a mano"}`; se agrega una entrada **solo cuando el precio cambia** (y la primera lectura). Máximo 200 por publicación (se descartan las más viejas).
- Guardá también `est["lecturas"][nombre] = {"fecha", "precio", "envio", "vendedor", "item_id", "error"}` de la última lectura (para mostrar en la centralita).

### A2. Precio cargado a mano
`POST /admin/proveedores/{nombre}/precio` con `{"precio": int}` (de 1 a 10.000.000; `nombre` tiene que existir en `proveedores.json`, si no 404).
- Sirve para cuando el usuario ve en ML un precio distinto del que lee el vigilante (por ejemplo, con los beneficios de su cuenta). Se guarda en `est["a_mano"][nombre] = {"precio", "fecha", "leido_entonces": <precio que leía el vigilante en ese momento>}` y va al historial con `"fuente": "a mano"`.
- Mientras exista, el vigilante usa ese precio como costo de la publicación. **Se descarta solo** cuando el vigilante lee un precio distinto de `leido_entonces` (el proveedor cambió el precio: la corrección ya no vale), y avisa por ntfy: "Cambió el precio de {nombre}: dejé de usar el que cargaste a mano".
- `DELETE /admin/proveedores/{nombre}/precio` lo quita.
- Después de cargarlo o quitarlo, corré el ajuste de ese producto en el momento (sin esperar 30 minutos).

### A3. Cambios grandes: aprobar o rechazar
Hoy, si el precio nuevo difiere más de 40 % del actual, `_ajustar_producto` no lo cambia y solo avisa.
- Guardá `est["pendientes"][producto] = {"vigente", "nuevo", "costo", "publicacion", "fecha"}`.
- `POST /admin/proveedores/pendientes/{producto}/aprobar` → aplica `nuevo` con `ajustar` y lo quita de pendientes.
- `POST /admin/proveedores/pendientes/{producto}/rechazar` → deja el precio como está y recuerda el costo rechazado: mientras el costo leído siga siendo ese, no vuelve a avisar ni a dejarlo pendiente.
- Si el costo cambia otra vez, el pendiente se recalcula.

### A4. `GET /admin/proveedores`
Por publicación: `nombre`, `producto`, `marco`, `url`, `item_id`, `vendedor`, última lectura (A1), precio a mano (A2), historial (A1). Por producto: precio vigente, pendiente (A3) y la regla de precio de `proveedores.json`. Más `comision_mp` (la que usa el vigilante, como en `/admin/costos`) y la hora de la última revisión.

### A5. Seguimiento del cuadro al cliente
- Migración (`MIGRACIONES` en `db.py`): `seguimiento TEXT`, `seguimiento_url TEXT`, `cuadro_comprado TEXT`.
- `POST /admin/pedidos/{pid}/seguimiento` con `{"numero": str, "url": str | null, "empresa": str | null}`. Solo pedidos de productos con `envio` (cuadros) y en `aprobado` o `entregado` (409 si no). `numero` de 4 a 60 caracteres sin saltos de línea (422); `url`, si viene, `https://` (422 si no).
- Guarda los tres campos (`cuadro_comprado` = ahora) y manda **un** mail al cliente (`avisos.mandar_mail`), en voseo y sin prometer fechas: "¡Hola {nombre}! Tu cuadro del pedido {pid} ya está en camino. Número de seguimiento: {numero}{ (empresa)}{, seguilo acá: url}. Cualquier duda, respondé este mail." Y un aviso por ntfy con el botón "Mandar WhatsApp" con ese mismo texto (`avisos.link_whatsapp`).
- Si el pedido ya tenía seguimiento: actualiza y vuelve a mandar solo si el cuerpo trae `"reenviar": true`; si no, 409 "ya tiene seguimiento".
- Agregá `seguimiento`, `seguimiento_url` y `cuadro_comprado` a los campos de `GET /admin/pedidos`.

### A6. Tests (`tienda/tests/test_tienda.py`, con `entorno`)
Historial solo con cambios; precio a mano usado como costo y descartado cuando cambia la lectura (con aviso); aprobar y rechazar un pendiente (rechazado no vuelve a avisar con el mismo costo); `/admin/proveedores` sin token 401; seguimiento: 409 en pedido sin cuadro o en estado equivocado, 422 con número o url inválidos, un mail al cliente, 409 al repetir sin `reenviar`.

### A7. Subida
Como siempre, a la carpeta que usa el servicio (paso 0): `pytest` ("4 failed, N passed" con las 4 de siempre) y `systemctl restart tutienditaia`.

## B. Centralita

### B1. Proveedores (habilitá la pestaña)
Como el prototipo: una tarjeta por producto con sus publicaciones.
- Por publicación: precio leído, envío, vendedor, hora de lectura, link "Ver en ML" (abre en el navegador), y un gráfico chico del historial (SVG simple, sin librerías externas). Si hay precio a mano: "Usando $X cargado a mano el dd/mm (el vigilante lee $Y)" y botón "Quitar".
- "Corregir a mano": campo de pesos + Guardar (confirmación dentro de la página) → A2.
- Si el producto tiene pendiente: "El costo pasó a $C: el precio tendría que ir de $V a $N (más de 40 %)" con "Aprobar" y "Rechazar" (confirmación) → A3.
- Arriba: "Revisar ahora" → `POST /admin/vigilante` (real: puede ajustar precios, decilo en el botón: "Revisar y ajustar ahora") y la comisión de MP con la que se calculan los precios.
- Estas acciones no son de un pedido: no van a ningún `historial.txt`; quedan en el historial de precios del servidor (A1).

### B2. Cuadro comprado → seguimiento al cliente
En Acciones → Cuadro (ya tiene seguimiento y "¿Cuánto pagaste?"):
- Campos: número de seguimiento (obligatorio para mandar), empresa (opcional), link (opcional).
- Botón "Guardar y mandarle el seguimiento al cliente" con confirmación dentro de la página que muestra el texto exacto que le va a llegar → A5. El monto pagado se sigue guardando como en la fase 2.
- Si ya tenía seguimiento: lo muestra y ofrece "Reenviar".
- Historial del pedido: "Seguimiento enviado al cliente: {numero}".
- En Hoy, el pedido de cuadro sale de "Tu turno" cuando tiene `seguimiento` (además de "Cuadro comprado" en el historial, que ya existe).

### B3. Clientes (pestaña nueva)
Con `/admin/pedidos` y `/admin/pagos` (sin pedidos `pendiente_pago` ni `cancelado`):
- Un cliente = mismo mail **o** mismo WhatsApp normalizado.
- Por cliente: nombre (el del último pedido), mail, WhatsApp, cantidad de pedidos, marcas (fotos / canción), total cobrado real (de los pagos; "sin dato" si falta alguno), primer y último pedido, y los pedidos (clic → ficha).
- Arriba: "Volvieron a comprar: N clientes" y filtro "solo los que volvieron".
- **Sin recordatorios ni mensajes**: para escribirles más adelante hace falta el permiso del cliente en el formulario (lo decide el usuario aparte).

### B4. Pruebas (`centralita/tests/test_centralita.py`, sin red ni `C:\Pedidos`)
Agrupar clientes por mail o WhatsApp; total "sin dato" si falta un pago; proveedores con pendiente y precio a mano (servidor simulado); seguimiento: la confirmación manda exactamente lo que se mostró (el texto viene del servidor o se arma igual en los dos lados: elegí uno y probalo).

### B5. Verificación con datos reales (solo mirando)
Proveedores con las 6 publicaciones reales y su historial (al principio va a tener una sola entrada). Clientes con los pedidos reales. **No cargues precios a mano, no apruebes ni rechaces, no mandes seguimientos.** Capturas en `centralita/capturas/` (en `.gitignore`; se borran después de la revisión).

## C. Entrega
- `centralita/ENTREGA.md`, sección "Fase 3": pruebas del servidor y de la centralita, lo verificado con datos reales, dudas.
- `tienda/docs/ENTREGA-ANTIGRAVITY.md`: "Tarea 15 hecha (fase 3 de la centralita)" con el paso 0, la subida y `pytest`.
- Subí también las dos páginas de fotos (`web/restauraciondefotos/index.html` e `index-base.html`: cambió el precio escrito del enmarcado 20x30 a $24.900, el que se ve un instante antes de que cargue el precio en vivo).
