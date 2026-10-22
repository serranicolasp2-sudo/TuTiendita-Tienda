# Tarea 11 para Antigravity: Centralita, fase 1 (pedidos y archivos)

Esta vez **programás vos**. Claude revisa al final y corrige. Si la tarea 10 (revisión del mail) no está hecha, hacela primero: es independiente y ya está probada.

**Leé antes de empezar:** `centralita/PLAN.md` (reglas que no se negocian y piezas que hay que reusar), el prototipo `centralita/prototipo.html` (abrilo en el navegador: es la referencia visual y de comportamiento; tiene datos inventados, la app real usa datos reales) y `DECISIONES.md` D-44 a D-47.

**Al terminar, frená.** No sigas con la fase 2. Dejá `centralita/ENTREGA.md` con qué hiciste, qué probaste y la salida de las pruebas, qué quedó pendiente y tus dudas. No toques `.env`, `DATOS_DIR`, las llaves del Escritorio ni la contraseña de root. Nada de pedidos de prueba en el servidor ni mails a clientes.

---

## A. Servidor (`tienda/app/`): cuatro endpoints nuevos

Seguí el estilo de `main.py`: `_admin(authorization)` en todos; errores de datos como `{"error", "campo"}` con 422, igual que `ErrorCampo`.

1. **Migración:** `ALTER TABLE pedidos ADD COLUMN cambios_extra INTEGER NOT NULL DEFAULT 0` (en `MIGRACIONES` de `db.py`). `flujo.cambios_max(p)` suma `p.get("cambios_extra") or 0`. Sumá `cambios_extra`, `aprobado`, `entregado`, `entrega_url` y `marca` a los campos que devuelve `GET /admin/pedidos`.
2. **`PATCH /admin/pedidos/{pid}/contacto`** con JSON `{"email"?: str, "whatsapp"?: str}`. El mail se valida con `correo.problema(email, revisado=True)`: el admin no necesita la sugerencia, pero el DNS sí tiene que dar bien. El WhatsApp se valida con `avisos.normalizar_whatsapp`, con largo de 12 a 15, igual que en `crear_pedido`. Devuelve el pedido actualizado.
3. **`POST /admin/pedidos/{pid}/reenviar`** con JSON `{"que": "vista_previa" | "entrega"}`. Reenvía el último mail y el aviso por ntfy con el botón de WhatsApp, **sin subir nada a Drive**. Sacá el armado del mail de `flujo.enviar_vista_previa` y de `flujo.entregar` a dos funciones (`_mail_vista_previa(cfg, p, extra)` y `_mail_entrega(cfg, p, link, extra)`), y usalas en los dos lados. Responde 409 si no hay `vista_url` o `entrega_url`.
4. **`POST /admin/pedidos/{pid}/cambio`** con JSON `{"texto": str, "sin_costo": bool = true}`. Pide un cambio en nombre del cliente. Solo se puede si el pedido está en `vista_previa`; si no, 409 con el estado. Con `sin_costo`, primero suma 1 a `cambios_extra`, así no le gasta un cambio al cliente. Después usa `flujo.registrar_respuesta(cfg, base, pid, "cambio", texto)`.
5. **`POST /admin/pedidos/{pid}/cambios-extra`** con JSON `{"cantidad": 1}` (de 1 a 3). Suma cambios incluidos para que el cliente pueda pedir otro desde su página de revisión. Solo en `vista_previa` o `cambio`. Devuelve cuántos le quedan.
6. **Tests** en `tienda/tests/test_tienda.py`, con el fixture `entorno`:
   - cada endpoint funcionando;
   - 401 sin token;
   - 409 y 422 en los casos de arriba;
   - el cambio sin costo no descuenta del cliente;
   - `reenviar` no llama a `drive.subir`.
7. **Subida al servidor**, igual que en las tareas 9 y 10:
   - copiá `app/` y `tests/`;
   - corré `pytest`: con los precios de prueba de $500 el esperado es "4 failed, N passed", con las 4 fallas de siempre;
   - `systemctl restart tutienditaia`.

## B. Centralita (programa local, carpeta `RegalosIA/centralita/`)

### Estructura
```
centralita/
  app.py                 FastAPI: API local en /api/... y la interfaz en /
  servicios/servidor.py  llamadas al servidor (usa pedidos.cliente(); nunca expone el token)
  servicios/locales.py   carpetas, historial, bot-estado.json (usa produccion/carpetas.py)
  servicios/archivos.py  listar, clasificar, leer y guardar con las reglas de abajo; rutas seguras
  servicios/audio.py     vista previa y final (reusa produccion/cancion.py)
  servicios/retoque.py   reemplazar una foto por un retoque y rearmar final y vista previa (reusa produccion/fotos.py)
  servicios/sistema.py   estado del bot, Codex, Claude, servidor y ML; reiniciar el bot; abrir el Explorador
  static/                index.html, app.js, estilos.css (la interfaz del prototipo, sin datos inventados)
  tests/test_centralita.py
  centralita.bat         arranca el servicio y abre la ventana
  ENTREGA.md
```
Python 3.11 de la PC (`C:\Users\Nicolás\AppData\Local\Programs\Python\Python311`), que ya tiene fastapi, uvicorn, httpx y Pillow. Agregá al `sys.path` `tienda/herramientas` y `produccion`, igual que `bot.py`.

### Seguridad del servicio local
- **Solo `127.0.0.1:8790`.**
- **Defensa contra otros sitios:** todas las rutas `/api` piden el encabezado `X-Centralita: 1` y verifican que `Host` sea `127.0.0.1:8790` o `localhost:8790`. Sin CORS. Así una página web cualquiera no puede disparar acciones en tu PC.
- **Rutas de archivo:** llegan como relativas a la carpeta del pedido. Se resuelven con `Path.resolve()` y tienen que quedar dentro de `carpetas.buscar(pid)`; si no, 400.
- **Llaves:** ni el token de admin ni las otras llaves llegan al navegador, a los logs ni a la respuesta de ningún endpoint.

### Qué muestra (datos reales)
Pedidos de `GET /admin/pedidos`, más `C:\Pedidos\bot-estado.json` y la carpeta local de cada pedido. Se excluyen `pendiente_pago` y `cancelado`.

**Columna y "qué falta" de cada pedido** (`est` = entrada del pedido en `bot-estado.json`):

| Columna | Caso | Qué falta |
|---|---|---|
| Tu turno | `est.intentos >= 3` | "El bot se frenó" + última línea del historial. En la fase 1 solo se muestra; no edites `bot-estado.json`, porque el bot lo reescribe. |
| Tu turno | RF en `cambio` y `est.cambio_en_espera == p.cambios` | "El bot no entendió el cambio: «nota_cambio»". Se resuelve con Acciones → instrucción. |
| Tu turno | TC en `pagado` o `cambio` y `est.letra_n > est.previa_subida` (o sin previa) | "Letra v{letra_n} lista: pegala en Suno y soltá el audio de la vista previa". |
| Tu turno | TC en `aprobado` sin MP3 en `4-entrega` | "Aprobó: falta la descarga oficial de Suno". |
| Tu turno | RF entregado con "Falta comprar el cuadro" en el historial y sin "Cuadro comprado" | Comprar el cuadro, con el link de `proveedores.link_compra(producto, marco)`. |
| Esperando al cliente | `vista_previa` | Hace cuánto se mandó. |
| Entregados | `entregado`, últimos 30 días | — |
| El bot trabajando | El resto (`pagado`, `cambio`, `aprobado` de fotos) | Última línea del historial. |

**Plazo:** desde `pagado` hasta la primera vista previa (`vista_n == 0`): fotos 2 h, canción 48 h, combo (`tc-combo`) 72 h. Barra verde, amarilla (más de 60 % del plazo) o roja (más de 85 % o vencido).

**Pantallas:**
- **Hoy:** lo de "Tu turno" y los plazos que corren.
- **Pedidos:** las 4 columnas, con filtro Fotos/Canciones y búsqueda por número o nombre.
- **Ficha del pedido:**
  - Resumen: datos del pedido y contacto.
  - Historial: `historial.txt` como línea de tiempo.
  - Archivos.
  - Acciones.
- **Sistema.**

Plata, Costos, Proveedores y ML/Meta quedan para la fase 2 o después. En el menú pueden aparecer deshabilitados con "Próximamente".

### Archivos: mencionar, abrir, mostrar en la carpeta (pedidos A y B del usuario)
- **Menciones:** todo nombre de archivo del pedido que aparezca en el historial, en "qué falta" o en Archivos se muestra como en el prototipo. **El nombre abre el archivo en una pestaña de la app.** El ícono de carpeta llama a `POST /api/pedidos/{pid}/mostrar?ruta=…`, que corre `explorer /select,"<ruta completa>"`: el Explorador se abre con el archivo seleccionado.
- **"Abrir con su programa":** `os.startfile(ruta)`.
- **Pestañas:** van arriba, como en el prototipo. Un punto marca cambios sin guardar. Al cerrar con cambios pregunta, dentro de la página: Guardar / Cerrar sin guardar / Seguir editando.
- **Clasificación y reglas:**
  - **Pedido entregado o cancelado:** todo es de solo lectura, salvo las notas del historial.
  - **Pedido en la columna "El bot trabajando":** se puede editar, pero al guardar responde 409 "el bot está trabajando en este pedido".

| Archivo | Se ve como | Al guardar o actuar |
|---|---|---|
| `historial.txt` | texto, solo lectura | Campo "Agregar una nota" → `carpetas.anotar(base, "Nota tuya: …")` |
| `pedido.txt`, `1-datos/pedido.txt` | texto, solo lectura | — |
| `2-letra/suno.txt` y `2-letra/letra-v{N}.txt` con N = `est.letra_n` (la actual) | texto editable | Ver "Sincronizar la letra actual" abajo. |
| `2-letra/letra-v{k}.txt` con k < N | texto editable | Solo guarda el archivo. El bot no hace nada. |
| `2-letra/version-v*.json`, `0-analisis/*` | solo lectura (JSON con formato) | — |
| `1-original/*` | imagen, solo lectura | — |
| `2-codex/foto-XX.png` (no `anteriores`) | imagen, con "Comparar con la original" (deslizador, como en el prototipo, contra `1-original/foto-XX.*`) | "Reemplazar por mi retoque": ver abajo. |
| `anteriores/*`, `3-entrega/*.jpg` | imagen, solo lectura | — |
| `*.mp3`, `*.wav`, `*.mp4` | reproductor, servido con `FileResponse` | — |
| Otro texto de hasta 1 MB | solo lectura | — |
| Lo demás | sin vista | "Abrir con su programa" |

**Sincronizar la letra actual:**
1. Leé `2-letra/version-v{N}.json` con `letras.leer_version`.
2. Si se editó `suno.txt`, sacá de sus secciones (`STYLE OF MUSIC:`, `EXCLUDE STYLES (en Más opciones):`, `LYRICS:`, `FONÉTICA:`) los campos `estilo`, `excluir`, `letra` y `foneticas`. Si se editó `letra-v{N}.txt`, actualizá solo `letra`.
3. Llamá a `letras.guardar_version(carpeta_letra, N, version, extra)`, conservando en `extra` los campos que no son de la letra: `revisor`, `correcciones`, `observaciones` y `cambio`. Así quedan iguales el `.txt`, el `.json` y `suno.txt`.
4. Anotá en el historial: "Editaste a mano <archivo>: el bot usa esta versión como base del próximo cambio".
5. Mostrá ese mismo aviso en la pestaña.

**Retoque de una foto** (`POST /api/pedidos/{pid}/retoque`):
1. Validá que el archivo sea una imagen con Pillow.
2. Mové `2-codex/foto-XX.png` a `2-codex/anteriores/foto-XX-v{n}.png`, con la misma numeración que usa `bot.restaurar_una`.
3. Guardá el retoque como `foto-XX.png`.
4. Rearmá final, vista previa y comparativa con `fotos.procesar`. Sumale a `procesar` dos parámetros opcionales: `estado="Pendientes"` (que se pase a `carpetas.carpeta`) y `solo=None` (los stems a procesar), así no repite Real-ESRGAN en todo el pack.
5. Anotá en el historial.
6. Si el pedido está en `pagado`, `cambio` o `vista_previa`, ofrecé "Mandar la vista previa al cliente": sube todos los `3-entrega/*-vista-previa.jpg` con el `POST /admin/pedidos/{pid}/vista-previa` del servidor, como hace `bot.mandar_vista_previa_fotos`.

### Soltar audios (pedido del usuario: cualquier nombre, se renombra solo)
En Archivos de los pedidos TC hay una zona para soltar el archivo. Valida con `ffprobe` que sea audio.
- **Vista previa** (pedido en `pagado` o `cambio`; en otro estado avisá que el bot no la va a subir):
  - El nombre es `3-vistas-previas\v{K}-previa.mp3`, con K = el mayor que ya exista + 1.
  - Se corta a `cancion.SEGUNDOS` (60 s), con el mismo fundido y los mismos metadatos que `cancion.previa`: `afade` de entrada 0,3 s y de salida 4 s, 128k, título "Vista previa · Tu Canción". **La vista previa nunca es la canción completa.**
  - Se anota en el historial. El bot la sube solo en su próxima vuelta.
- **Botón "Grabar lo que suena":** la alternativa sin descargar de Suno. Corre `python produccion/cancion.py previa <pid>` en segundo plano y muestra el estado: "dale play en Suno…", "grabando…", "listo".
- **Final** (solo si el pedido está en `aprobado`):
  - Pide "Para quién" (sugerencia: `datos.para_quien` hasta el primer " - " o ","), con "Tu canción para {para}.mp3" de ejemplo.
  - Usa la lógica de `cancion.final`: copia con metadatos a `4-entrega`. El bot entrega solo.

### Acciones (pestaña de la ficha)
- **Instrucción para rehacer:**
  - Pedido en `vista_previa`: `POST /admin/pedidos/{pid}/cambio` con `sin_costo=true`.
  - Pedido RF en `cambio` con el bot esperando: escribe `nota-cambio.txt`, como `pedidos.py cambio`.
  - Otro estado: explicá por qué no se puede.
  - En todos los casos se anota en el historial.
- **Dar un cambio extra sin costo:** `POST /admin/pedidos/{pid}/cambios-extra`.
- **Contacto:** mail y WhatsApp editables. En el navegador, el mail muestra la sugerencia como en `tienda.js`. Al guardar llama al `PATCH /admin/pedidos/{pid}/contacto` y ofrece "Reenviar el último mail" (`POST /reenviar`). Muestra los errores del servidor tal cual.
- **Copiar mensaje para WhatsApp:** copia el texto con `navigator.clipboard`.
- **Cuadro** (solo RF con envío): link al proveedor y "Marcar comprado" con número de seguimiento. En la fase 1 **solo se anota en el historial**: "Cuadro comprado. Seguimiento …". El aviso al cliente es de la fase 3.

### Sistema
- **Bot:**
  - Si está vivo: proceso con `bot.py` en la línea de comando, buscado con PowerShell `Get-CimInstance Win32_Process`.
  - Hora de la última línea de `C:\Pedidos\bot.log`.
  - Botón "Reiniciar", con confirmación dentro de la página: frena el proceso y lo vuelve a arrancar con `pythonw.exe bot.py`, desde `tienda/herramientas`, desconectado del servicio.
- **Codex:** si `codexcli.codex_exe()` lo encuentra.
- **Claude:** `claude auth status` → `loggedIn`. No muestres otra cosa.
- **Servidor:** `GET /salud`.
- **Mercado Libre:** `ml_api.get("/users/me")` → solo el `nickname`.
- **Carpetas:** cantidad de pedidos por RF/TC y Pendientes/Listos.

### Arranque
- **`centralita.bat`:** si el puerto 8790 no responde, levanta `pythonw -m uvicorn app:app --host 127.0.0.1 --port 8790` desde `centralita/`, espera a que responda y abre `msedge --app=http://127.0.0.1:8790`.
- **Acceso directo:** "Centralita" en el Escritorio (no en Inicio), apuntando al `.bat`, con un ícono genérico de Windows.

## C. Pruebas
- **`centralita/tests/test_centralita.py`**, sin red y sin tocar `C:\Pedidos`:
  - Una carpeta temporal como `carpetas.PEDIDOS`, un `bot-estado.json` de ejemplo y un servidor falso.
  - Columnas y "qué falta" para cada caso de la tabla.
  - Plazos.
  - Rutas con `..` o absolutas → 400.
  - Falta `X-Centralita` → 403.
  - Clasificación de archivos.
  - Sincronización de `suno.txt` ↔ `letra-v{N}.txt` ↔ `version-v{N}.json`.
  - Numeración de las vistas previas (genera un WAV corto con ffmpeg).
  - Retoque: la versión vieja va a `anteriores`. Simulá `fotos.procesar` para no correr Real-ESRGAN.
  - Pedido entregado: todo de solo lectura.
- **Con los pedidos reales, solo mirando** (anotá el resultado en `ENTREGA.md`):
  - RF-0010 y TC-0002 aparecen en Entregados con su historial.
  - En TC-0002, `suno.txt` abre en una pestaña de solo lectura.
  - "Mostrar en la carpeta" abre el Explorador con el archivo seleccionado.
  - Sistema muestra el bot vivo y Claude con sesión.
  - **No reinicies el bot ni guardes nada en pedidos reales.**
- **Capturas** de Hoy, Pedidos, una ficha, el visor de texto, el comparador de fotos y Sistema, en `centralita/capturas/`. Ojo: tienen datos de clientes, así que van en `.gitignore` y se borran después de la revisión.

## D. Entrega
`centralita/ENTREGA.md` con:
- la salida de `pytest` del servidor y de la centralita;
- qué verificaste a mano;
- qué quedó distinto del prototipo y por qué;
- tus dudas.

Al final de `tienda/docs/ENTREGA-ANTIGRAVITY.md` anotá "Tarea 11 hecha (fase 1 de la centralita)" con la salida de la subida al servidor.
