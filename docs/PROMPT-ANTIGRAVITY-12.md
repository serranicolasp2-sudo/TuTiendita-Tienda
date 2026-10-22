# Tarea 12 para Antigravity: Centralita, fase 2 (plata y costos reales)

Programás vos; Claude revisa al final. **Leé antes:** `centralita/PLAN.md` (reglas que no se negocian), `centralita/ENTREGA.md` §6 (lo que se corrigió de la fase 1: no repitas esos errores), el prototipo `centralita/prototipo.html` (pantallas Plata y Costos por venta) y `centralita/cargos-ml-2026-10-14.json` (lectura real de ML del 14/10, sirve para comparar).

**Al terminar, frená.** Dejá en `centralita/ENTREGA.md` una sección "Fase 2" con qué hiciste, la salida de las pruebas, qué verificaste con datos reales, qué quedó distinto y tus dudas. No toques `.env`, `DATOS_DIR`, las llaves del Escritorio ni la contraseña de root. Nada de pedidos de prueba en el servidor ni mails a clientes.

## La regla de esta fase: solo datos reales
El usuario lo pidió así: *"Las comisiones quiero las reales, para inventarlas prefiero que no me informe nada."*
- Toda cifra de costos sale de una API (Mercado Pago, Mercado Libre), de una lectura del vigilante o de un monto que cargó el usuario. Cada cifra muestra **fuente y fecha** (en un `title` o en una línea chica abajo).
- Si no hay dato: **"sin dato"**. Nunca porcentajes de referencia, promedios de internet, ni "aproximado".
- Las cuentas (restar, sumar, buscar el precio que iguala) se pueden hacer, siempre que **todos** los números que entran sean reales. Si uno falta, el resultado es "sin dato" y se dice cuál falta.
- El precio que publica un proveedor **no es** lo que pagó el usuario: se muestra como "publicado hoy a $X (vigilante, hh:mm)", nunca como costo del pedido.

## Lecciones de la fase 1 (obligatorias)
1. Lo que mostrás en `ENTREGA.md` como verificado tiene que estar verificado de verdad: si una captura muestra un error, no está andando.
2. Nunca uses un nombre o una ruta que llegue del navegador como parte de una ruta de archivo.
3. El servicio local es `centralita/servicio.py` (`uvicorn servicio:app`). No crees ningún módulo llamado `app.py` en `centralita/`.
4. Los `.bat` van en ASCII (sin acentos) y con CRLF.
5. Nada nuevo en el navegador que no pase por `api()` con `X-Centralita` (imágenes y audios: `urlDeArchivo`).

---

## 0. Primero: subir las webs (quedó pendiente de la tarea 10)
Parte B de `tienda/docs/PROMPT-ANTIGRAVITY-10.md`: las 4 páginas (`web/tucancion/index.html` e `index-base.html`, `web/restauraciondefotos/index.html` e `index-base.html`) a `/var/www/html/public/tutienditaia/...`. Verificación:
```bash
B=https://campuscfp401avellaneda.com.ar/tutienditaia
curl -s $B/tucancion/ | grep -c 'id="por-que"'                  # 1
curl -s $B/restauraciondefotos/ | grep -c 'corregimos mirando'  # 1
```

## A. Servidor (`tienda/app/`)

1. **`GET /admin/pagos`** (con `_admin`). Para cada pedido con `mp_pago` (opcional `?desde=YYYY-MM-DD` sobre `pagado`), consulta `mp.obtener_pago(cfg, mp_pago)` y devuelve **solo esta lista blanca** de campos (nada del pagador: ni mail, ni documento, ni nombre, ni tarjeta):
   ```json
   {"pedido": "RF-0010", "producto": "...", "precio": 500, "pago": "123", "estado": "approved", "detalle": "accredited",
    "medio": "account_money", "tipo_medio": "account_money", "cuotas": 1, "monto": 500.0,
    "comisiones": [{"tipo": "mercadopago_fee", "monto": 21.51, "a_cargo": "collector"}],
    "neto": 478.49, "reembolsado": 0.0, "liberacion": {"fecha": "2026-11-01T...", "estado": "pending"},
    "aprobado": "2026-10-14T..."}
   ```
   Origen en el pago de MP: `status`, `status_detail`, `payment_method_id`, `payment_type_id`, `installments`, `transaction_amount`, `fee_details[]` (`type`, `amount`, `fee_payer`), `transaction_details.net_received_amount`, `transaction_amount_refunded`, `money_release_date`, `money_release_status`, `date_approved`.
   - Caché en memoria por id de pago: 10 minutos; los pagos con `money_release_status == "released"` no cambian más (sin vencimiento).
   - Si MP falla para un pago: ese pedido viene con `"error": "Mercado Pago 4xx/5xx"` y el resto sigue.
   - El token de MP no aparece en la respuesta, en el log ni en los errores.
2. **`GET /admin/costos`** (con `_admin`): lo que el servidor sabe para el simulador.
   ```json
   {"productos": {"rf-cuadro-ecocuero-20x30": {"nombre": "...", "precio": 34900}, ...},
    "proveedores": {"leido": "<mtime de proveedores-estado.json, ISO>",
                    "publicaciones": [{"producto": "...", "nombre": "...", "url": "https://meli.la/...", "publicado": 25000}]}}
   ```
   `precio` = el vigente de `catalogo.PRODUCTOS`. `publicado` = `estado["costos"][nombre]` del vigilante (`cfg.datos_dir / "proveedores-estado.json"`); si no hay lectura, `null`.
3. **Tests** en `tienda/tests/test_tienda.py` con el fixture `entorno` y `mp.obtener_pago` simulado: 401 sin token; la respuesta trae solo los campos de la lista blanca (armá un pago falso con `payer` y `card` y verificá que no salen); un pago que falla no rompe la lista; la caché no vuelve a llamar a MP; `/admin/costos` con y sin lectura del vigilante.
4. **Subida:** como siempre (`app/` y `tests/`, `pytest`: "4 failed, N passed" con las 4 de siempre, `systemctl restart tutienditaia`).

## B. Centralita

### B1. Plata (habilitá la pestaña)
Una fila por pedido cobrado (de `/admin/pagos`, cruzado con `/admin/pedidos`), del más nuevo al más viejo, con filtro por mes y por marca:

| Columna | De dónde sale |
|---|---|
| Pedido, fecha, marca, producto | servidor |
| Canal | "Web (Mercado Pago)". Las ventas por ML llegan en la fase 4. |
| Cobrado | `monto` |
| Comisión MP | suma de `comisiones` (con el detalle en el `title`) y el % sobre el monto |
| Proveedor | solo para cuadros: lo que cargó el usuario al marcarlo comprado (ver B3). Si no cargó: **"sin dato"** y, abajo y en gris, "publicado hoy a $X" del vigilante. Fotos digitales y canciones: "—" (no tienen proveedor). |
| Te quedó | `neto` − proveedor. Si el proveedor es "sin dato", la celda dice "sin dato (falta lo que pagaste el cuadro)". |
| Liberación | "Liberada" o "Se libera el dd/mm" (`liberacion`), y "Reembolsado $X" si `reembolsado > 0` |

Arriba, totales del filtro **solo con filas completas**: cobrado, comisiones, te quedó, por liberar (suma de `neto` con liberación pendiente y la fecha más cercana). Si hay filas incompletas, decí cuántas quedaron afuera de "te quedó".

Debajo: **"Lo que cobró Mercado Pago, según cómo te pagaron"**, agrupado por `tipo_medio` (dinero en cuenta, débito, crédito en 1 cuota, crédito en N cuotas, efectivo…). Por cada grupo: cantidad de pagos, % real (suma de comisiones / suma de montos) y días promedio hasta la liberación. Los tipos sin pagos no aparecen. Fuente: "tus N pagos, del dd/mm al dd/mm".

### B2. Costos por venta (habilitá la pestaña)
Un bloque por producto del catálogo (de `/admin/costos`), más un simulador de precio libre.

**En la web (Mercado Pago):**
- Precio vigente.
- Comisión MP: el % real de B1 **para cada medio de pago que ya tenga pagos**, como filas ("si paga con dinero en cuenta: te quedan $X · 4,30 % real, 6 pagos"). Si todavía no hay pagos de ese medio, no se inventa: no aparece.
- Proveedor (cuadros): "publicado hoy a $X" del vigilante, con la hora de lectura, y la aclaración "lo que vas a pagar si lo comprás hoy". Si no hay lectura: "sin dato".

**En Mercado Libre (simulado con la API, desde la PC):**
- `ml_api.get("/sites/MLA/listing_prices", price=P, category_id=C)` → para `gold_special` (Clásica) y `gold_pro` (Premium): `sale_fee_amount` y su detalle (`percentage_fee`, `fixed_fee`, `financing_add_on_fee`).
- Categorías en `centralita/categorias-ml.json` (nuevo, editable a mano): packs de fotos `MLA434385`, cuadros `MLA1635`, canciones `null`. Sin categoría: todo el bloque ML dice "sin dato: falta la categoría de ML" (no la adivines).
- "Te queda en ML" = precio − cargo de ML − proveedor (publicado hoy). **Envío: "sin dato"** (falta medida y peso del paquete; ML no cotiza sin eso). IVA de los cargos: "sin dato".
- **"A cuánto publicar en ML para que te quede lo mismo que en la web"**: el primer precio terminado en 900 desde el precio de la web, de a $1.000, hasta 3 veces el precio, cuyo `precio − cargo` (consultado a la API para ese precio) sea ≥ lo que queda en la web con el **% real de dinero en cuenta**. Si todavía no hay pagos con dinero en cuenta, no se calcula ("sin dato: hace falta un cobro real por la web"). Como el envío es "sin dato", aclaralo al lado: "sin contar el envío".
- Comparalo con `cargos-ml-2026-10-14.json`: con los mismos precios tienen que dar los mismos cargos (si ML cambió las tarifas, anotalo en ENTREGA).
- Caché de las consultas a ML en `centralita/datos/ml-cargos.json` (`{"<precio>|<categoría>": {"respuesta": ..., "leido": ISO}}`), válida 24 h. Botón **"Actualizar desde las APIs"**: borra la caché y vuelve a consultar MP (vía `/admin/pagos`), ML y `/admin/costos`. `centralita/datos/` va en `.gitignore`. Sin datos de clientes ahí.

**Simulador:** elegís producto (o "otro" con categoría de ML a mano) y escribís un precio: muestra lo mismo que arriba para ese precio.

Aviso fijo en esta pantalla (información para una decisión del usuario, no cambies nada): "El vigilante calcula los precios de los cuadros suponiendo que MP se lleva un 8 % (`NETO_MP = 0,92`). Lo real de tus cobros con dinero en cuenta es X %." (con el X de B1, o sin el aviso si no hay pagos).

### B3. Cuadro comprado con el monto real
En Acciones → Cuadro, agregá "¿Cuánto pagaste?" (pesos, entero, opcional) al lado del número de seguimiento.
- Se guarda en `C:\Pedidos\costos-proveedor.json` (`{"RF-0012": {"pagado": 25000, "fecha": ISO, "fuente": "cargado a mano"}}`), con escritura atómica (temporal + `replace`).
- Va al historial: "Cuadro comprado. Pagaste $25.000. Seguimiento …".
- Si ya había un monto, el nuevo lo reemplaza y el historial dice "corregiste lo que pagaste: $A → $B".
- Plata usa este monto como "Proveedor".

### B4. Reintentar un pedido con el bot frenado (pendiente de la fase 1)
El bot saltea para siempre un pedido con `intentos >= 3` en `bot-estado.json`, y ese archivo lo reescribe el bot: la centralita **no lo edita**.
- **Bot (`tienda/herramientas/bot.py`, cambio chico):** en `pasada()`, antes del `continue` de los frenados, si existe `reintentar.txt` en la carpeta del pedido (`carpetas.buscar(pid)`): lo mueve a `0-analisis/reintentar-<fecha>.txt` (no se borra), pone `intentos = 0`, anota en el historial "Reintento pedido desde la centralita" y sigue con el pedido en esa misma pasada.
- **Centralita:** en "Tu turno", en los pedidos frenados, botón "Reintentar" (con confirmación dentro de la página) → escribe `reintentar.txt` con la fecha y la anota en el historial. El texto de "qué falta" pasa a "Reintento pedido: el bot lo toma en su próxima vuelta (cada 60 s)" mientras el archivo exista.
- No reinicies el bot real para probarlo: test con `bot-estado.json` y carpetas temporales (simulá `paso`).

### B5. Pruebas (`centralita/tests/test_centralita.py`, sin red y sin tocar `C:\Pedidos`)
- Plata: totales solo con filas completas; cuadro sin monto → "sin dato" en Proveedor y en Te quedó; % por medio de pago con pagos falsos.
- Costos: sin pagos de dinero en cuenta no calcula "a cuánto publicar"; con `listing_prices` simulado encuentra el precio correcto (armá un caso a mano); categoría `null` → "sin dato"; caché de 24 h y "Actualizar" la invalida.
- Cuadro: guardar y corregir el monto (historial con los dos valores); escritura atómica.
- Reintentar: el bot pone `intentos = 0`, mueve `reintentar.txt` a `0-analisis/` y procesa el pedido; sin el archivo, lo sigue salteando.
- Que ninguna respuesta de `/api/...` traiga datos del pagador ni el token de MP.

### B6. Verificación con datos reales (solo mirando)
- Plata con los pagos reales: el % de dinero en cuenta tiene que dar 4,30 % (lectura del 14/10: 6 pagos de $500, $21,51 de comisión cada uno). Si da otra cosa, anotá los números.
- Costos por venta: los cargos de ML para los precios de hoy, comparados con `cargos-ml-2026-10-14.json`.
- No marques cuadros comprados ni pidas reintentos en pedidos reales.
- Capturas de Plata y Costos por venta en `centralita/capturas/` (en `.gitignore`; tienen datos de clientes: se borran después de la revisión). **Miralas antes de anotarlas como verificadas.**

## C. Entrega
- `centralita/ENTREGA.md`, sección "Fase 2": salida de `pytest` del servidor y de la centralita, lo verificado con datos reales (con los números), diferencias con el prototipo, dudas.
- Al final de `tienda/docs/ENTREGA-ANTIGRAVITY.md`: "Tarea 12 hecha (fase 2 de la centralita)" con la salida de la subida y del paso 0.
