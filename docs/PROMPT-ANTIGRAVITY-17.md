# Tarea 17 para Antigravity: precios a mano desde la centralita + fechas importantes para recordatorios

Programás vos; Claude revisa al final. **Leé antes:** `centralita/PLAN.md`, `centralita/ENTREGA.md` §6, §8 y §10 (lo que se corrigió en las fases anteriores: no lo repitas), `DECISIONES.md` D-49 a D-51. **Urgente: tiene que estar andando antes del Día de la Madre (18/10)**, así se guardan las fechas de esos compradores. Si algo te frena, entregá primero la parte C (fechas) y avisá.

**Al terminar, frená** y dejá en `centralita/ENTREGA.md` la sección "Fase 3b" (qué hiciste, pruebas, qué verificaste con datos reales, dudas). No toques `.env`, las llaves ni la contraseña de root. **Nada de pedidos de prueba, ni mails o recordatorios a clientes reales.** El código del servidor se sube solo a `/srv/tutienditaia/app/app/`.

Decisiones del usuario (14/10):
1. **Precios a mano desde la centralita de TODOS los productos y servicios**, no solo los cuadros. Son los 10 del catálogo (`catalogo.PRODUCTOS`; si se suma uno, aparece solo):
   - Fotos: `rf-foto-1` (1 foto), `rf-pack-5`, `rf-pack-10`, `rf-pack-20`.
   - Cuadros: `rf-cuadro-enmarcado-20x30`, `rf-cuadro-enmarcado-30x40`, `rf-cuadro-ecocuero-20x30`, `rf-cuadro-ecocuero-40x30`.
   - Canciones: `tc-cancion`, `tc-combo`.

   En los productos sin proveedor se cambia el precio y listo. En los cuadros se elige **fijo** o **automático con la ganancia que elija**. Es prioridad del usuario, junto con las fechas.
2. Fechas: **solo de la persona del regalo** (no la del comprador).
3. Recordatorio: **mail automático** + **WhatsApp que manda el usuario** (aviso con el mensaje ya escrito).

Recordatorios de siempre: solo datos reales ("sin dato" si falta); nada del navegador como ruta; todo por `api()` con `X-Centralita`; lo que anotás como verificado lo miraste de verdad.

---

## A. Servidor: precios a mano

Hoy: `POST /admin/precios` cambia precios en bloque (`catalogo.guardar_precios` → `DATOS_DIR/precios.json`); el vigilante ajusta los cuadros solo, con la regla de `proveedores.json` (`ganancia_neta` o `costo_base`/`precio_base`) y la comisión real de MP (D-49).

1. **Modo y ganancia por producto en `DATOS_DIR/precios-modo.json`** (no en `proveedores.json`: ese archivo es código y se pisa en cada subida). `{"rf-cuadro-enmarcado-20x30": {"modo": "fijo" | "auto", "ganancia_neta": int | null, "fecha": ISO}}`. Sin entrada = automático con la regla de `proveedores.json`.
2. **Vigilante** (`_ajustar_producto` y `_ajustar_un_producto`), con el candado que ya tiene:
   - `fijo`: no cambia el precio. Si con el costo y la comisión real lo que queda (`precio × (1 − tasa) − costo`) es menor que la ganancia de la regla, avisa **una vez por costo**: "Con el costo nuevo ($C), el precio fijo de $P te deja $Q por venta (la regla pide $G)".
   - `auto` con `ganancia_neta`: usa esa en lugar de la de la regla.
3. **Historial de cambios de precio** en `DATOS_DIR/precios-historial.jsonl`, una línea por cambio: `{"fecha", "producto", "antes", "despues", "quien": "a mano" | "vigilante" | "aprobado"}`. Lo escriben el cambio a mano, el ajuste del vigilante y la aprobación de un pendiente.
4. **`GET /admin/precios`**: por producto del catálogo: `id`, `nombre`, `marca`, `precio` vigente, `con_proveedor` (si está en `proveedores.json`), `modo`, `ganancia_neta` efectiva y su origen ("regla" o "a mano"), y los últimos 50 cambios del historial.
5. **`POST /admin/precios/{producto}`**, con `_admin`:
   - `{"precio": int}` (de 100 a 1.000.000): producto sin proveedor → cambia el precio. Cuadro → lo pone en `fijo` con ese precio.
   - `{"modo": "auto", "ganancia_neta": int | null}` (solo cuadros; de 0 a 1.000.000; `null` = volver a la regla): recalcula en el momento con el último costo leído (o el cargado a mano) y la comisión real.
   - 404 si el producto no existe; 422 con `{"error", "campo"}` si un dato está mal.
   - Responde el producto como en el punto 4.
   - Los pedidos ya creados no cambian de precio (como hoy).

## B. Centralita: pantalla "Precios"
Pestaña nueva (entre "Costos por venta" y "Proveedores"), con **los 10 productos** agrupados en Fotos, Cuadros y Canciones.
- Tabla: producto, precio vigente, modo (Automático / Fijo, en cuadros), "te queda por venta" con la comisión real de dinero en cuenta (y el costo del proveedor en cuadros, con la misma lógica que Costos por venta: precio a mano si hay, si no el leído), botón "Cambiar".
- "Cambiar" abre un cuadro **dentro de la página**:
  - productos sin proveedor: campo de precio;
  - cuadros: "Precio fijo" (campo de precio) o "Automático" (campo de ganancia neta, vacío = la regla).
  - Mientras escribís, muestra lo que te quedaría en la web (comisión real) y en ML Clásica/Premium (usá `POST /api/costos/simular`, que ya existe), con la fuente y la fecha de cada dato.
  - Aclaración fija: "Rige en el momento para los pedidos nuevos; los que ya están hechos mantienen su precio. La web se actualiza sola."
    Es cierto por D-51: todo precio de las webs tiene `data-precio` y lo pinta `tienda.js` con el del servidor, incluidos el "por foto" de los packs, el resumen del formulario y la barra del celular. Las descripciones para Google y para compartir en redes (`<meta>`) ya no llevan precios (Claude los sacó el 14/10, así no quedan viejos). **Si agregás un precio nuevo en las páginas, ponele `data-precio`.**
  - Paquetes: al cambiar un pack, mostrá también el nuevo "por foto" (precio ÷ cantidad) y que su precio por foto sea menor que el de la foto suelta; si no, avisá (no frena).
  - Confirmar → `POST /admin/precios/{producto}`.
- Abajo: historial de cambios (fecha en hora de Argentina, producto, antes → después, quién).

## C. Fechas importantes (web + servidor + centralita)

### C1. Formulario (las dos webs, `index.html` e `index-base.html`)
Los formularios ya piden `para_quien`, `vinculo` y `ocasion`. Agregá, después de "ocasión", un bloque **opcional** "¿Te avisamos para la próxima?":
- `fecha_tipo`: Cumpleaños / Aniversario / Otra fecha (con `fecha_otra`, texto de hasta 40 caracteres, visible solo con "Otra fecha").
- `fecha_dia` (1 a 31) y `fecha_mes` (enero a diciembre). **Sin año.**
- `fecha_permiso` (casilla **sin tildar**): "Acepto que me escriban por mail o WhatsApp unos días antes de esa fecha para recordármela. Me puedo dar de baja cuando quiera."
- Si cargan la fecha sin tildar el permiso, un aviso debajo (no frena la compra): "Para guardar la fecha necesitamos tu permiso."
- En el celular el formulario va por pasos (`movil.js`): el bloque tiene que quedar dentro de un paso y los pasos tienen que seguir andando. Corré `produccion/pruebas/probar_pasos_movil.py` y anotá la salida.
- En "Condiciones y garantías" de las dos webs, en Privacidad, sumá una línea: "Recordatorios: solo si nos das permiso en el formulario. Guardamos el día y el mes (sin año), para quién es y tu contacto, y te podés dar de baja desde cualquier mensaje."

### C2. Servidor
- Tabla nueva `fechas` (en `db.py`, con su migración): `id`, `pedido`, `creado`, `nombre`, `email`, `whatsapp`, `marca`, `para_quien`, `vinculo`, `tipo`, `otra`, `dia`, `mes`, `permiso_en`, `permiso_texto` (versión del texto aceptado, "v1"), `baja_token` (`secrets.token_urlsafe(24)`), `baja_en`, `ultimo_aviso_anio`.
- En `crear_pedido`:
  - **Solo si `fecha_permiso == "si"` y hay día y mes válidos** se guarda una fila.
  - **Sin permiso no se guarda la fecha en ningún lado** (tampoco en los datos del pedido).
  - Validá: día y mes que existan (31/4 o 30/2 → 422 `campo: fecha_dia`; 29/2 sí vale); `tipo` de la lista; `otra` hasta 40 caracteres.
- **Recordatorio diario**, en el ciclo de fondo de la tienda (como el vigilante y la conciliación), una vez por día:
  - Fechas con permiso, sin baja, cuya próxima ocurrencia cae **en 15 días**, y sin aviso este año (`ultimo_aviso_anio`). El 29/2, en años no bisiestos, cuenta como 28/2.
  - **Mail al comprador** con la marca del pedido original y en voseo, sin prometer precios ni plazos, y el link de baja al pie. Por ejemplo: "¡Hola {nombre}! Se viene el cumpleaños de {para_quien} (el {dia} de {mes}). Si querés regalarle otra vez algo con su historia, acá estamos: {link de la web}." Al pie: "¿No querés más recordatorios? {link de baja}".
  - **Aviso por ntfy al usuario**, con el botón "Mandar WhatsApp" y un texto equivalente (sin el link de baja; sí "si no querés que te escriba más por esto, avisame").
  - Marcá `ultimo_aviso_anio` después de mandar.
- **Baja:** `GET /baja/{token}` muestra una página con un botón "Dejar de recibir recordatorios" (no cambia nada: los lectores de mail abren los links solos). El `POST /baja/{token}` marca `baja_en` y muestra "Listo, no te vamos a escribir más por esta fecha". Token inválido → 404. Estilo como la página de revisión (`_pagina_revision`).
- **`GET /admin/fechas`** (con `_admin`): las fechas con permiso y sin baja, con la próxima ocurrencia y los días que faltan; cantidades por `tipo` y por `vinculo`; y las fechas comerciales del año con su día calculado: Día de la Madre (3.er domingo de octubre), Día del Padre (3.er domingo de junio), Día del Niño (3.er domingo de agosto), San Valentín (14/2) y Navidad (25/12). Cada una con cuántos contactos con permiso tienen un vínculo que corresponda (Madre: mamá/madre; Padre: papá/padre; San Valentín: pareja/novio/novia/esposo/esposa; el resto: todos).

### C3. Centralita: pestaña "Fechas"
- Próximos 30 días: fecha (dd/mm), tipo, para quién, vínculo, comprador y contacto, "aviso enviado este año: sí/no".
- Fechas comerciales con cuántos contactos con permiso hay para cada una.
- Cantidades por tipo y vínculo.
- Solo mirar: en esta tarea no se manda nada desde la centralita.

## D. Pruebas
- **Servidor** (`tienda/tests/test_tienda.py`):
  - **Precios:** a mano sin proveedor; cuadro a fijo (el vigilante no lo toca y avisa una sola vez si el costo deja menos ganancia); volver a automático con ganancia propia (recalcula); historial; 401; 404; 422.
  - **Fechas:**
    - sin permiso no se guarda nada; con permiso, sí;
    - 31/4 → 422; 29/2 sí vale;
    - el recordatorio sale solo a 15 días y una vez por año, y sin repetirse si se corre dos veces el mismo día;
    - el 29/2 en un año no bisiesto;
    - con baja no sale;
    - `GET /baja` no cambia nada y `POST /baja` sí;
    - `/admin/fechas` con las fechas comerciales bien calculadas para 2026 (Madre 18/10, Padre 21/6, Niño 16/8).
- **Centralita:** Precios (están los 10 productos; te queda con la comisión real; cuadro fijo y automático; aviso de pack más caro por foto que la foto suelta); Fechas (próximos 30 días y conteos).

## E. Subida (en este orden)
1. Servidor: `app/` y `tests/` → `/srv/tutienditaia/app/app/`. `pytest` **todo en verde** (hoy son 36 pruebas más las tuyas) y `systemctl restart tutienditaia`. Van también los arreglos de la revisión de la fase 3 que dejó Claude (`vigilante.py`: hora de la última revisión con zona horaria).
2. Páginas: `web/tucancion/` y `web/restauraciondefotos/` (`index.html` e `index-base.html`) y `web/movil.js` si lo tocaste.
3. Verificación con datos reales (solo mirar):
   - `GET /admin/precios` y la pantalla Precios con los precios reales.
   - `GET /admin/fechas`: vacío al principio. Eso está bien: no hagas pedidos de prueba.
   - Las dos webs muestran el bloque de fechas en computadora y en celular.
   - Capturas en `centralita/capturas/` (en `.gitignore`). Miralas antes de anotarlas.

## F. Entrega
- `centralita/ENTREGA.md`, sección "Fase 3b": salida de las pruebas del servidor, de la centralita y de `probar_pasos_movil.py`, lo verificado y las dudas.
- `tienda/docs/ENTREGA-ANTIGRAVITY.md`: "Tarea 17 hecha" con la subida.
