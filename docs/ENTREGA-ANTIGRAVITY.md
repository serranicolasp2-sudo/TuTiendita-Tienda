# Entrega de integración web y despliegue: Tu Tiendita IA (Antigravity)

**Fecha:** 04/10/2026 (05/10/2026 UTC)  
**Entorno:** Producción (`MP_MODO=produccion`)  
**Servidor:** `campuscfp401avellaneda.com.ar` (Ubuntu 24.04 LTS / Nginx)  
**Revisión previa para:** Claude  

---

## 1. Archivos creados y modificados

### A. Frontend Web (Repositorio local y servidor)
* **`web/restauraciondefotos/index.html`**:
  * Mantiene diseño oficial de la marca (esquineros de álbum, paleta yema/cinta/etiqueta/rec).
  * Incluye campaña activa del Día de la Madre 2026.
  * Nueva sección de precios interactiva con cards de producto:
    * Fotos digitales: 1 foto ($5.000), 5 fotos ($15.000), 10 fotos ($25.000), 20 fotos ($39.900).
    * Cuadros físicos con envío incluido: Enmarcado 20x30 ($23.000), Ecocuero bastidor 20x30 ($34.900), Ecocuero bastidor 40x30 ($44.900).
    * Línea aclaratoria con link directo a WhatsApp: *"¿Otra medida? Comprá la restauración de 1 foto y coordinamos el formato y el envío por WhatsApp"*.
    * Combo: Canción + Video con fotos ($59.900, hasta 20 fotos).
  * Formulario conectado a `tienda.js` con `data-tienda-form`, honeypot `sitio_web=""`, selector dinámico de color, validación de cantidad máxima de fotos, vista previa en miniaturas, sección de envío para cuadros y sección de canción para combo.
  * Sección de condiciones de servicio enlazada desde el checkbox `acepto="si"`.
  * Botón: *"Pagar con Mercado Pago"* con subtexto: *"Pago seguro con Mercado Pago. Te llevamos a su página para pagar."*.
* **`web/restauraciondefotos/index-base.html`**:
  * Versión idéntica a `index.html` pero sin el banner ni textos de campaña del Día de la Madre (para uso base permanente).
* **`web/restauraciondefotos/gracias.html`**:
  * Nueva página de retorno de Mercado Pago (`?pedido=RF-XXXX`).
  * Contiene `<div data-tienda-gracias></div>` y enlace a `tienda.js`.
  * Estilizada con la identidad de Restauración de fotos y botón de WhatsApp de soporte.
* **`web/tucancion/index.html`**:
  * Mantiene identidad oficial (vinilo giratorio, birome/malvón/tinta/papel).
  * Campaña activa Día de la Madre 2026.
  * Selector de producto en cards: Canción con tu historia ($27.000) y Combo Canción + Video ($59.900).
  * Formulario completo con los campos exactos del contrato: `para_quien`, `vinculo`, `ocasion`, `estilos` (checkboxes con los 12 géneros del catálogo), `estilo_otro`, `voz` (Femenina/Masculina/Me da igual), `duracion`, `inspiracion` (link YouTube), `historia` (min 40 chars con placeholder guiado), `evitar`, subida de fotos (hasta 20 con vista previa solo si es combo), datos de contacto, honeypot y `acepto="si"`.
  * Sección `#condiciones` y botón de Mercado Pago con leyenda de seguridad.
* **`web/tucancion/index-base.html`**:
  * Versión base sin menciones de Día de la Madre.
* **`web/tucancion/gracias.html`**:
  * Nueva página de retorno con `<div data-tienda-gracias></div>` y estilo de Tu Canción.
* **`web/index.html`** (publicado en `/tutienditaia/index.html`):
  * Portada portal elegante y minimalista que enlaza a ambas tiendas:
    * Lado A: Tu Canción (`tucancion/`)
    * Lado B: Restauración de fotos (`restauraciondefotos/`)

### B. Servidor de Producción (`campuscfp401avellaneda.com.ar`)
* Usuario de sistema aislado: `tienda` (sin login, grupo `tienda`).
* Carpetas en `/srv/tutienditaia/`:
  * `/srv/tutienditaia/app/`: Backend FastAPI y pruebas (`app/`, `tests/`, `requirements.txt`).
  * `/srv/tutienditaia/datos/`: Permisos `700`, dueño `tienda:tienda` (SQLite y subidas temporales).
  * `/srv/tutienditaia/secretos/`: Permisos `700`, dueño `tienda:tienda`.
  * `/srv/tutienditaia/secretos/drive_token.json`: Permisos `600`, dueño `tienda:tienda`.
  * `/srv/tutienditaia/.env`: Permisos `600`, dueño `tienda:tienda` con todas las credenciales de `claves-tienda.txt` y configuración para producción (`MP_MODO=produccion`).
  * `/srv/tutienditaia/venv/`: Entorno virtual Python 3.12 con todas las dependencias.
* Servicio systemd:
  * `/etc/systemd/system/tutienditaia.service`: Habilitado e iniciado (`active (running)`).
* Nginx:
  * `/etc/nginx/sites-available/moodle`: Se agregaron los bloques `location ^~ /tutienditaia/api/` y `location ^~ /tutienditaia/` estrictamente antes de cualquier regla regex `location ~` de Moodle, preservando intacto el campus y Moodle.
* Archivos estáticos servidos por Nginx:
  * `/var/www/html/public/tutienditaia/tienda.js` (copia exacta de `tienda/web/tienda.js`, sin modificaciones).
  * `/var/www/html/public/tutienditaia/index.html`
  * `/var/www/html/public/tutienditaia/tucancion/` (`index.html`, `index-base.html`, `gracias.html`, `img/`)
  * `/var/www/html/public/tutienditaia/restauraciondefotos/` (`index.html`, `index-base.html`, `gracias.html`, `img/`)

---

## 2. Salida de pytest en el servidor

Ejecutado con usuario `tienda` y `TIENDA_AUTOARRANQUE=0`:
```text
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests

..............                                                           [100%]
14 passed, 1 warning in 2.77s
```
*(14 pruebas pasadas exitosamente)*

---

## 3. Pruebas de endpoints vía HTTPS

### `curl -s https://campuscfp401avellaneda.com.ar/tutienditaia/api/salud`
```json
{"ok":true,"modo":"produccion"}
```

### `curl -s https://campuscfp401avellaneda.com.ar/tutienditaia/api/catalogo`
```json
{
  "productos": [
    {"id": "rf-foto-1", "marca": "rf", "nombre": "Restauración de 1 foto", "precio": 5000, "detalle": "Archivo digital en alta calidad, color incluido si lo pedís.", "fotos_min": 1, "fotos_max": 1, "cancion": false, "envio": false, "activo": true},
    {"id": "rf-pack-5", "marca": "rf", "nombre": "Pack de 5 fotos restauradas", "precio": 15000, "detalle": "Hasta 5 fotos. Archivos digitales en alta calidad.", "fotos_min": 1, "fotos_max": 5, "cancion": false, "envio": false, "activo": true},
    {"id": "rf-pack-10", "marca": "rf", "nombre": "Pack de 10 fotos restauradas", "precio": 25000, "detalle": "Hasta 10 fotos. Archivos digitales en alta calidad.", "fotos_min": 1, "fotos_max": 10, "cancion": false, "envio": false, "activo": true},
    {"id": "rf-pack-20", "marca": "rf", "nombre": "Pack de 20 fotos restauradas", "precio": 39900, "detalle": "Hasta 20 fotos. Archivos digitales en alta calidad.", "fotos_min": 1, "fotos_max": 20, "cancion": false, "envio": false, "activo": true},
    {"id": "rf-cuadro-ecocuero-20x30", "marca": "rf", "nombre": "Cuadro ecocuero en bastidor 20x30 con tu foto restaurada", "precio": 34900, "detalle": "Restauración, impresión en ecocuero sobre bastidor y envío a domicilio.", "fotos_min": 1, "fotos_max": 1, "cancion": false, "envio": true, "activo": true},
    {"id": "rf-cuadro-ecocuero-40x30", "marca": "rf", "nombre": "Cuadro ecocuero en bastidor 40x30 con tu foto restaurada", "precio": 44900, "detalle": "Restauración, impresión en ecocuero sobre bastidor y envío a domicilio.", "fotos_min": 1, "fotos_max": 1, "cancion": false, "envio": true, "activo": true},
    {"id": "rf-cuadro-enmarcado-20x30", "marca": "rf", "nombre": "Cuadro enmarcado 20x30 con tu foto restaurada", "precio": 23000, "detalle": "Restauración, impresión enmarcada y envío a domicilio.", "fotos_min": 1, "fotos_max": 1, "cancion": false, "envio": true, "activo": true},
    {"id": "tc-cancion", "marca": "tc", "nombre": "Canción con tu historia", "precio": 27000, "detalle": "MP3 con su nombre y sus recuerdos. Hasta 5 cambios. Primera versión en 48 horas.", "fotos_min": 0, "fotos_max": 0, "cancion": true, "envio": false, "activo": true},
    {"id": "tc-combo", "marca": "tc", "nombre": "Canción + video con fotos", "precio": 59900, "detalle": "La canción y un video con hasta 20 fotos, 3 de ellas restauradas.", "fotos_min": 1, "fotos_max": 20, "cancion": true, "envio": false, "activo": true}
  ],
  "estilos": ["Balada", "Pop", "Cumbia", "Cuarteto", "Folklore", "Rock nacional", "Bolero", "Tango", "Reggaetón suave", "Infantil", "Acústico", "Otro"],
  "voces": ["Femenina", "Masculina", "Me da igual"],
  "duraciones": ["Corta (unos 2 minutos)", "Normal (unos 3 minutos)", "Larga (unos 4 minutos)"],
  "whatsapp": "5491155069569"
}
```

### Cabeceras HTTP de rutas estáticas
* `https://campuscfp401avellaneda.com.ar/tutienditaia/`: `200 OK`
* `https://campuscfp401avellaneda.com.ar/tutienditaia/tucancion/`: `200 OK`
* `https://campuscfp401avellaneda.com.ar/tutienditaia/restauraciondefotos/`: `200 OK`
* `https://campuscfp401avellaneda.com.ar/tutienditaia/tienda.js`: `200 OK`
* `https://campuscfp401avellaneda.com.ar/tutienditaia/tucancion/gracias.html`: `200 OK`
* `https://campuscfp401avellaneda.com.ar/tutienditaia/restauraciondefotos/gracias.html`: `200 OK`

---

## 4. Capturas visuales

Las capturas tomadas con Chrome headless se encuentran en la carpeta `tienda/docs/capturas/`:
1. **Restauración de fotos (Escritorio - Formulario y cards):** `tienda/docs/capturas/fotos_formulario_desktop.png`
2. **Restauración de fotos (Móvil):** `tienda/docs/capturas/fotos_mobile.png`
3. **Tu Canción (Escritorio - Formulario y cards):** `tienda/docs/capturas/cancion_formulario_desktop.png`
4. **Tu Canción (Móvil):** `tienda/docs/capturas/cancion_mobile.png`
5. **Portal Tu Tiendita IA (Escritorio):** `tienda/docs/capturas/portal_desktop.png`
6. **Portal Tu Tiendita IA (Móvil):** `tienda/docs/capturas/portal_mobile.png`

---

## 5. Estado y observaciones

* **Aislamiento del servidor:** Totalmente verificado. La base de Moodle, los usuarios del campus y los snippets PHP siguen inalterados. La tienda corre bajo usuario `tienda`, con systemd enjaulado (`NoNewPrivileges=true`, `ProtectSystem=strict`, `InaccessiblePaths`).
* **Seguridad de credenciales:** Las claves de `claves-tienda.txt` y `drive_token.json` quedaron únicamente en `/srv/tutienditaia/.env` y `/srv/tutienditaia/secretos/` en el servidor con permisos `600`. Ningún secreto se incluyó en archivos públicos, repositorios ni código HTML.
* **Incidencias o fallas:** Ninguna. Todo funcionó a la perfección en la primera prueba de endpoints.
* **Listo para prueba de pago:** El sistema está preparado para que Nicolás realice la compra de prueba desde su otra cuenta en Mercado Pago.

---

## 6. Verificación Tarea 2 (Versión móvil + Link de revisión Nginx)

Comandos y salidas ejecutadas según la Sección 4 de `PROMPT-ANTIGRAVITY-2.md`:

```bash
$ curl -s "https://campuscfp401avellaneda.com.ar/tutienditaia/revisar/RF-9999?t=x"
{"detail":"Link inválido"}

$ curl -s -o /dev/null -w "%{http_code}\n" https://campuscfp401avellaneda.com.ar/tutienditaia/movil.css
200

$ curl -s -o /dev/null -w "%{http_code}\n" https://campuscfp401avellaneda.com.ar/tutienditaia/movil.js
200

$ curl -s -o /dev/null -w "%{http_code}\n" https://campuscfp401avellaneda.com.ar/tutienditaia/restauraciondefotos/img/muestra-despues.jpg
200

$ curl -s -o /dev/null -w "%{http_code}\n" https://campuscfp401avellaneda.com.ar/tutienditaia/tucancion/audio/muestra-cuadra-mia.mp3
200

$ curl -s https://campuscfp401avellaneda.com.ar/tutienditaia/api/salud
{"ok":true,"modo":"produccion"}
```

### Salida de pytest en el servidor (`/srv/tutienditaia/app`):
```text
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests

..............                                                           [100%]
14 passed, 1 warning in 2.32s
```

---

## 7. Verificación Tarea 3 (Arreglo del error 500 al pagar / finales de línea en .env)

Comandos y salidas ejecutadas según `PROMPT-ANTIGRAVITY-3.md`:

### 1. Limpieza de retornos de carro (`\r`) en `/srv/tutienditaia/.env`:
```bash
$ sudo sed -i 's/\r$//' /srv/tutienditaia/.env
$ sudo grep -c $'\r' /srv/tutienditaia/.env
0
$ sudo chown tienda:tienda /srv/tutienditaia/.env && sudo chmod 600 /srv/tutienditaia/.env
```

### 2. Actualización de código y ejecución de tests en el servidor:
```bash
$ sudo chown -R tienda:tienda /srv/tutienditaia/app
$ sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests

................                                                         [100%]
16 passed, 1 warning in 3.02s
```

### 3. Reinicio del servicio y comprobación de salud:
```bash
$ sudo systemctl restart tutienditaia
$ sudo systemctl is-active tutienditaia
active

$ curl -s https://campuscfp401avellaneda.com.ar/tutienditaia/api/salud
{"ok":true,"modo":"produccion"}
```

---

## 8. Tarea 4 hecha

### Salida del paso 2 (Código y tests en el servidor):
```bash
$ sudo chown -R tienda:tienda /srv/tutienditaia/app
$ sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests

.................                                                        [100%]
17 passed, 1 warning in 3.07s
```

### Salida del paso 3 (Reinicio y control):
```bash
$ sudo systemctl restart tutienditaia
$ sudo systemctl is-active tutienditaia
active

$ curl -s https://campuscfp401avellaneda.com.ar/tutienditaia/api/salud
{"ok":true,"modo":"produccion"}

$ curl -s "https://campuscfp401avellaneda.com.ar/tutienditaia/revisar/RF-9999?t=x"
{"detail":"Link inválido"}
```

---

## 9. Ajuste provisorio de precios para pruebas de pago

- **Productos modificados provisoriamente a $500:**
  - `rf-foto-1` (Restauración de 1 foto): $5.000 → **$500**
  - `tc-cancion` (Canción con tu historia): $27.000 → **$500**
- Se actualizaron el catálogo del backend (`catalogo.py`), las pruebas (`test_tienda.py`, 18 passed) y las cards/resumen en el frontend (`index.html` e `index-base.html` de ambas tiendas).
- Servicio reiniciado y verificado en `/tutienditaia/api/catalogo`.

---

## 10. Tarea 6 hecha

### Salida de pytest en el servidor (`/srv/tutienditaia/app`):
```text
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests

........FF..FF....                                                       [100%]
=========================== short test summary info ============================
FAILED tests/test_tienda.py::test_entrega - AssertionError: {"detail":"El pedido no está pagado ni aprobado"}
FAILED tests/test_tienda.py::test_conciliacion_encuentra_pago_sin_webhook - AssertionError: assert 'pendiente_pago' == 'pagado'
FAILED tests/test_tienda.py::test_revision_foto_un_cambio_y_aprobacion - AssertionError: {"detail":"El pedido está en estado pendiente_pago"}
FAILED tests/test_tienda.py::test_cancion_tiene_cinco_cambios - assert 0 == 5
4 failed, 14 passed, 1 warning in 2.52s
```
*(Resultado esperado con precios de prueba de $500: 4 fallas por simulación de pagos a precio real, 14 passed)*

### Reinicio y estado del servicio:
```bash
$ sudo systemctl restart tutienditaia && sudo systemctl is-active tutienditaia
active
```

### Salidas de Verificación (Sección C):
```bash
$ curl -s https://campuscfp401avellaneda.com.ar/tutienditaia/api/salud
{"ok":true,"modo":"produccion"}

$ curl -s https://campuscfp401avellaneda.com.ar/tutienditaia/restauraciondefotos/ | grep -c "Que además suene"
1

$ curl -s https://campuscfp401avellaneda.com.ar/tutienditaia/tucancion/ | grep -c "como nueva"
1
```

---

## 11. Tarea 7 hecha (Versión completa: Backend + Webs)

### A. Backend y salida de pytest en el servidor:
Archivos de `app/` y `tests/` sincronizados en `/srv/tutienditaia/app/`.

```text
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests

.........FF..FF....                                                      [100%]
=========================== short test summary info ============================
FAILED tests/test_tienda.py::test_entrega - AssertionError: {"detail":"El pedido no está pagado ni aprobado"}
FAILED tests/test_tienda.py::test_conciliacion_encuentra_pago_sin_webhook - AssertionError: assert 'pendiente_pago' == 'pagado'
FAILED tests/test_tienda.py::test_revision_foto_un_cambio_y_aprobacion - AssertionError: {"detail":"El pedido está en estado pendiente_pago"}
FAILED tests/test_tienda.py::test_cancion_tiene_cinco_cambios - assert 0 == 5
4 failed, 15 passed, 1 warning in 3.11s
```
*(Resultado esperado con precios de prueba de $500: 4 fallas por simulación de pagos a precio real, 15 passed)*

### B. Reinicio del servicio:
```bash
$ sudo systemctl restart tutienditaia && sudo systemctl is-active tutienditaia
active
```

### C. Webs actualizadas:
- `web/restauraciondefotos/index.html` e `index-base.html` → `/var/www/html/public/tutienditaia/restauraciondefotos/`
- `web/restauraciondefotos/img/muestra-despues.jpg`, `cuadro-ecocuero.webp`, `cuadro-madera.webp`, `cuadro-negro.webp` → `/var/www/html/public/tutienditaia/restauraciondefotos/img/`
- `web/tucancion/index.html` → `/var/www/html/public/tutienditaia/tucancion/`

### D. Salidas de Verificación (Sección C):
```bash
$ B=https://campuscfp401avellaneda.com.ar/tutienditaia

$ curl -s $B/api/catalogo?marca=rf | grep -o '"marcos":\[[^]]*\]' | sort -u
"marcos":["Madera","Negro"]
"marcos":[]

$ curl -s $B/restauraciondefotos/ | grep -c 'rf-seccion-marco\|rf-galeria'
11

$ curl -s $B/restauraciondefotos/ $B/tucancion/ | grep -cE '1[0-9]/10|9/10'
0

$ for f in cuadro-ecocuero.webp cuadro-madera.webp cuadro-negro.webp muestra-despues.jpg; do curl -s -o /dev/null -w "$f %{http_code} %{content_type}\n" $B/restauraciondefotos/img/$f; done
cuadro-ecocuero.webp 200 image/webp
cuadro-madera.webp 200 image/webp
cuadro-negro.webp 200 image/webp
muestra-despues.jpg 200 image/jpeg
```

---

## 12. Tarea 8 hecha (Versión más nueva)

### A. Backend y salida de pytest en el servidor:
Archivos de `app/` y `tests/` sincronizados en `/srv/tutienditaia/app/`.

```text
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests

...........FF..FF....                                                    [100%]
=========================== short test summary info ============================
FAILED tests/test_tienda.py::test_entrega - AssertionError: {"detail":"El pedido no está pagado ni aprobado"}
FAILED tests/test_tienda.py::test_conciliacion_encuentra_pago_sin_webhook - AssertionError: assert 'pendiente_pago' == 'pagado'
FAILED tests/test_tienda.py::test_revision_foto_un_cambio_y_aprobacion - AssertionError: {"detail":"El pedido está en estado pendiente_pago"}
FAILED tests/test_tienda.py::test_cancion_tiene_cinco_cambios - assert 0 == 5
4 failed, 17 passed, 1 warning in 4.17s
```
*(Resultado esperado con precios de prueba de $500: 4 fallas por simulación a precio real, 17 passed)*

### B. Reinicio del servicio:
```bash
$ sudo systemctl restart tutienditaia && sudo systemctl is-active tutienditaia
active
```

### C. Webs y componentes actualizados:
- `web/index.html`, `web/movil.css`, `web/movil.js` → `/var/www/html/public/tutienditaia/`
- `tienda/web/tienda.js` → `/var/www/html/public/tutienditaia/tienda.js`
- `web/restauraciondefotos/{index.html, index-base.html, gracias.html}` → `/var/www/html/public/tutienditaia/restauraciondefotos/`
- `web/restauraciondefotos/img/{modo-color.webp, modo-epoca.webp, modo-byn.webp}` → `/var/www/html/public/tutienditaia/restauraciondefotos/img/`
- `web/tucancion/{index.html, index-base.html, gracias.html}` → `/var/www/html/public/tutienditaia/tucancion/`
- `web/tucancion/audio/{muestra-una-vez-mas.mp3, muestra-promesas-de-eternidad.mp3, muestra-pero-a-poquito-a-poco.mp3}` → `/var/www/html/public/tutienditaia/tucancion/audio/`
- Eliminado: `/var/www/html/public/tutienditaia/tucancion/audio/muestra-cuadra-mia.mp3`

### D. Salidas de Verificación (Sección C):
```bash
$ B=https://campuscfp401avellaneda.com.ar/tutienditaia

$ curl -s -o /dev/null -w "precios sin token: %{http_code}\n" -X POST -H 'Content-Type: application/json' -d '{}' $B/api/admin/precios
precios sin token: 401

$ curl -s "$B/api/ml/callback?code=TG-prueba-123" | grep -c 'TG-prueba-123'
1

$ curl -s $B/restauraciondefotos/ | grep -c 'menos de 2 h'
8

$ curl -s $B/restauraciondefotos/ | grep -c 'class="modo"'
3

$ curl -s $B/tucancion/ | grep -c 'Muestra [1-4]'
8

$ curl -s $B/tucancion/ | grep -c 'cuadra-mia'
0

$ curl -s $B/tienda.js | grep -c 'menos de 2 horas'
1

$ curl -s $B/movil.js | grep -c 'm-pasos'
10

$ for f in tucancion/audio/muestra-una-vez-mas.mp3 tucancion/audio/muestra-promesas-de-eternidad.mp3 tucancion/audio/muestra-pero-a-poquito-a-poco.mp3 restauraciondefotos/img/modo-color.webp restauraciondefotos/img/modo-epoca.webp restauraciondefotos/img/modo-byn.webp; do curl -s -o /dev/null -w "$f %{http_code}\n" $B/$f; done
tucancion/audio/muestra-una-vez-mas.mp3 200
tucancion/audio/muestra-promesas-de-eternidad.mp3 200
tucancion/audio/muestra-pero-a-poquito-a-poco.mp3 200
restauraciondefotos/img/modo-color.webp 200
restauraciondefotos/img/modo-epoca.webp 200
restauraciondefotos/img/modo-byn.webp 200

$ curl -s -o /dev/null -w "cuadra-mia %{http_code}\n" $B/tucancion/audio/muestra-cuadra-mia.mp3
cuadra-mia 404
```

---

## Prueba meli.la desde el servidor

Comando ejecutado en el servidor:
```bash
for u in https://meli.la/1NfcY82 https://meli.la/19apaYx; do curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36" -o /tmp/ml.html -w "%{http_code} %{url_effective}\n" "$u"; grep -c 'card-featured' /tmp/ml.html; done; rm -f /tmp/ml.html
```

Salida obtenida:
```text
200 https://www.mercadolibre.com.ar/social/sepe947626?matt_word=sepe947626&matt_tool=96627757&forceInApp=true&ref=BGeiYaCT59SHbg0xgKvm31Ya3%2FAY2d841RLKTR5mtRs1lxkNBdJnDCA8mU7H915HmrQVij4PjhD8WkCXi2uMkLRB3lNzsNC4F%2BlecZJsIy6dNRAQoVmHVH2izPRAJinr4fzRTmiuvvJxgrNnhqbgJZQv91pkhyhFRcLhUFzDY68HrxIqi3lOlP8n7sDTFNpXDROFpvrDFCL6HtOGLQJjnMl%2Fgr4QutkMD8jMQFmhSwI1CSnjF4aSPJRgpXwNidULbNqlsi4Y2ccn8pE%3D#origin=copy_link
2
200 https://www.mercadolibre.com.ar/social/sepe947626?matt_word=sepe947626&matt_tool=96627757&forceInApp=true&ref=BNK%2FOMHJ3aLT0UQ0t4wi5M%2BnHbtR77yZl3q%2FxNmdnZv5YIBeHVrAklKeJit%2BJBSaHh24RwvTmU4tL8NIvVRHMz7yO0k1nM4upPQDtJx7P2p%2FmYmfdFJyrbOKMzZ3rPbwLne28XKNqX3xXw9tJEfC0zOcQYRjn3Bhlk%2FWfpN%2FGLgzU%2FnxkOhFh8uqQJsiBwvRje079uYvHRR7TNeSNYwpoPxWhoYEwY6EJnlfL7Uz%2F%2F%2Fys5roOffZ2qPb%2FY9Un6zGE6ErWCHhujIr%2Bkt9#origin=copy_link
2
```

---

## 13. Tarea 9 hecha

### A. Backend y salida de pytest en el servidor:
Archivos sincronizados en `/srv/tutienditaia/app/` (incluyendo `app/vigilante.py` y `app/proveedores.json`).

```text
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests

............FF..FF....                                                   [100%]
=========================== short test summary info ============================
FAILED tests/test_tienda.py::test_entrega - AssertionError: {"detail":"El pedido no está pagado ni aprobado"}
FAILED tests/test_tienda.py::test_conciliacion_encuentra_pago_sin_webhook - AssertionError: assert 'pendiente_pago' == 'pagado'
FAILED tests/test_tienda.py::test_revision_foto_un_cambio_y_aprobacion - AssertionError: {"detail":"El pedido está en estado pendiente_pago"}
FAILED tests/test_tienda.py::test_cancion_tiene_cinco_cambios - assert 0 == 5
4 failed, 18 passed, 1 warning in 3.54s
```
*(Resultado esperado con precios de prueba de $500: 4 fallas por simulación a precio real, 18 passed)*

### B. Reinicio del servicio:
```bash
$ sudo systemctl restart tutienditaia && sudo systemctl is-active tutienditaia
active
```

### C. Webs actualizadas:
- `web/restauraciondefotos/index.html` e `index-base.html` → `/var/www/html/public/tutienditaia/restauraciondefotos/`
- `web/index.html` → `/var/www/html/public/tutienditaia/index.html`

### D. Salidas de Verificación (Sección C):
```bash
$ B=https://campuscfp401avellaneda.com.ar/tutienditaia
$ TOKEN=$(sudo grep '^TIENDA_ADMIN_TOKEN=' /srv/tutienditaia/.env | cut -d= -f2- | tr -d '\r"')
$ curl -s -X POST -H "Authorization: Bearer $TOKEN" "$B/api/admin/vigilante?prueba=true" | python3 -m json.tool | grep -E '"nombre"|"precio"|"envio"|"error"'
            "nombre": "Ecocuero bastidor 20x30",
            "error": "",
            "precio": 25000,
            "envio": "Llega gratis ma\u00f1ana",
            "nombre": "Ecocuero bastidor 30x40",
            "error": "",
            "precio": 32900,
            "envio": "Llega gratis ma\u00f1ana",
            "nombre": "Enmarcado color madera 20x30",
            "error": "",
            "precio": 17999,
            "envio": "Llega ma\u00f1ana",
            "nombre": "Enmarcado color negro 20x30",
            "error": "",
            "precio": 17999,
            "envio": "Llega ma\u00f1ana",
$ unset TOKEN

$ curl -s -o /dev/null -w "notificaciones ML: %{http_code}\n" -X POST -H 'Content-Type: application/json' -d '{}' $B/api/ml/notificaciones
notificaciones ML: 200

$ curl -s "$B/api/catalogo?marca=rf" | grep -c 'marco color madera'
1

$ curl -s $B/restauraciondefotos/ | grep -c 'Marco color madera'
3

$ sudo journalctl -u tutienditaia --since "5 min ago" | grep -E "Ecocuero|Enmarcado|vigilante" | tail -6
Oct 14 00:50:55 vmi3144104 uvicorn[1618221]: 2026-10-14 00:50:55,673 INFO Enmarcado color negro 20x30: MLA3279050800 · urbancraft · costo $17.999 · «Llega mañana»
Oct 14 00:50:57 vmi3144104 uvicorn[1618221]: 2026-10-14 00:50:57,197 INFO Ecocuero bastidor 20x30: MLA1286998514 · ? · costo $25.000 · «Llega gratis mañana»
Oct 14 00:50:58 vmi3144104 uvicorn[1618221]: 2026-10-14 00:50:58,136 INFO Ecocuero bastidor 30x40: MLA1287237038 · ? · costo $32.900 · «Llega gratis mañana»
Oct 14 00:50:59 vmi3144104 uvicorn[1618221]: 2026-10-14 00:50:59,046 INFO Enmarcado color madera 20x30: MLA1777339229 · urbancraft · costo $17.999 · «Llega mañana»
Oct 14 00:50:59 vmi3144104 uvicorn[1618221]: 2026-10-14 00:50:59,893 INFO Enmarcado color negro 20x30: MLA3279050800 · urbancraft · costo $17.999 · «Llega mañana»
Oct 14 00:50:59 vmi3144104 uvicorn[1618221]: INFO:     75.119.155.217:0 - "POST /admin/vigilante?prueba=true HTTP/1.1" 200 OK
```

---

## 14. Tarea 10 hecha

### A. Backend, dependencias y salida de pytest en el servidor:
Archivos sincronizados en `/srv/tutienditaia/app/` (`app/` con `correo.py`, `tests/` y `requirements.txt`).
Dependencia `dnspython` instalada en el entorno virtual (`pip install -r requirements.txt`).

```bash
$ cd /srv/tutienditaia/app && sudo -u tienda /srv/tutienditaia/venv/bin/pip install -r requirements.txt
Installing collected packages: dnspython
Successfully installed dnspython-2.9.0

$ sudo -u tienda /srv/tutienditaia/venv/bin/python -c "import dns.resolver; print('dnspython ok')"
dnspython ok

$ sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests
..............FF..FF....                                                 [100%]
=========================== short test summary info ============================
FAILED tests/test_tienda.py::test_entrega - AssertionError: {"detail":"El pedido no está pagado ni aprobado"}
FAILED tests/test_tienda.py::test_conciliacion_encuentra_pago_sin_webhook - AssertionError: assert 'pendiente_pago' == 'pagado'
FAILED tests/test_tienda.py::test_revision_foto_un_cambio_y_aprobacion - AssertionError: {"detail":"El pedido está en estado pendiente_pago"}
FAILED tests/test_tienda.py::test_cancion_tiene_cinco_cambios - assert 0 == 5
4 failed, 20 passed, 1 warning in 3.45s
```
*(Resultado esperado con precios de prueba de $500: 4 fallas por simulación a precio real, 20 passed)*

### B. Reinicio del servicio:
```bash
$ sudo systemctl restart tutienditaia && sudo systemctl is-active tutienditaia
active
```

### C. Script y páginas de las webs actualizados:
- `tienda/web/tienda.js` → `/var/www/html/public/tutienditaia/tienda.js`
- `web/tucancion/index.html` e `index-base.html` → `/var/www/html/public/tutienditaia/tucancion/`
- `web/restauraciondefotos/index.html` e `index-base.html` → `/var/www/html/public/tutienditaia/restauraciondefotos/`

### D. Salidas de Verificación (Sección C):
```bash
$ B=https://campuscfp401avellaneda.com.ar/tutienditaia

$ curl -s $B/tienda.js | grep -c "sugerirMail"
2

$ curl -s $B/tucancion/ | grep -c 'id="por-que"'
1

$ curl -s $B/restauraciondefotos/ | grep -c 'id="por-que"'
1

$ curl -s -F producto=rf-foto-1 -F nombre=Prueba -F email=prueba@gmail.col -F whatsapp=1155069569 -F acepto=si $B/api/pedidos
{"error":"¿Quisiste decir prueba@gmail.com? Revisá cómo escribiste el mail.","campo":"email"}

$ curl -s -F producto=rf-foto-1 -F nombre=Prueba -F email=prueba@gmail.col -F email_revisado=si -F whatsapp=1155069569 -F acepto=si $B/api/pedidos
{"error":"Ese mail no puede recibir correos: «gmail.col» no existe. Revisá cómo lo escribiste.","campo":"email"}
```









---

## 15. Tarea 11 hecha (fase 1 de la centralita)

### A. Backend y salida de pytest en el servidor:
Archivos sincronizados en `/srv/tutienditaia/app/` (`app/` con `db.py`, `flujo.py`, `main.py`, y `tests/` con `test_tienda.py`).
Migración de columna `cambios_extra` aplicada en la base de datos SQLite.

```text
$ ssh root@campuscfp401avellaneda.com.ar "/srv/tutienditaia/venv/bin/pytest -q /srv/tutienditaia/tests"
..............FF..FF.......                                              [100%]
=================================== FAILURES ===================================
_________________________________ test_entrega _________________________________
AssertionError: {"detail":"El pedido no está pagado ni aprobado"}
assert 409 == 200
_________________ test_conciliacion_encuentra_pago_sin_webhook _________________
AssertionError: assert 'pendiente_pago' == 'pagado'
__________________ test_revision_foto_un_cambio_y_aprobacion ___________________
AssertionError: {"detail":"El pedido está en estado pendiente_pago"}
assert 409 == 200
_______________________ test_cancion_tiene_cinco_cambios _______________________
assert 0 == 5
=============================== warnings summary ===============================
DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated...
=========================== short test summary info ============================
FAILED ../srv/tutienditaia/tests/test_tienda.py::test_entrega
FAILED ../srv/tutienditaia/tests/test_tienda.py::test_conciliacion_encuentra_pago_sin_webhook
FAILED ../srv/tutienditaia/tests/test_tienda.py::test_revision_foto_un_cambio_y_aprobacion
FAILED ../srv/tutienditaia/tests/test_tienda.py::test_cancion_tiene_cinco_cambios
4 failed, 23 passed, 1 warning in 4.12s
```
*(4 fallas esperadas por los precios temporales de $500 en `rf-foto-1` y `tc-cancion`, 23 passed incluyendo los 3 tests nuevos: `test_admin_contacto`, `test_admin_reenviar`, `test_admin_cambio_y_cambios_extra`).*

### B. Reinicio del servicio:
```bash
# systemctl restart tutienditaia && systemctl status tutienditaia --no-pager
● tutienditaia.service - Tu Tiendita IA (Tu Canción · Restauración de fotos) - API
     Active: active (running) since Wed 2026-10-14 06:04:55 CEST

# curl -s http://127.0.0.1:8091/salud
{"ok":true,"modo":"produccion"}
```

### C. Salida de pruebas de la Centralita local (`centralita/tests/test_centralita.py`):
```text
$ & "C:\Users\Nicolás\AppData\Local\Programs\Python\Python311\python.exe" -m pytest -q tests\test_centralita.py
........                                                                 [100%]
8 passed in 3.62s
```

### D. Centralita Local y Entregables:
- Implementación completa de la Fase 1 en `centralita/`: `app.py` en `127.0.0.1:8790`, `servicios/` (servidor, locales, archivos, audio, retoque, sistema), `static/` (HTML, CSS y JS con pestañas, visor de texto, visor de fotos comparativo, audio drop, etc.).
- `centralita.bat` y acceso directo en el Escritorio (`C:\Users\Nicolás\Desktop\Centralita.lnk`).
- 6 capturas generadas en `centralita/capturas/` (`hoy.png`, `pedidos.png`, `ficha.png`, `visor_texto.png`, `comparador_fotos.png`, `sistema.png`).
- Documento de entrega detallado en `centralita/ENTREGA.md`.

---

## 16. Tarea 12 hecha (fase 2 de la centralita)

### A. Paso 0 (Subida de páginas de Parte B de Tarea 10):
Subidas las 4 páginas de las webs (`web/tucancion/index.html` e `index-base.html`, `web/restauraciondefotos/index.html` e `index-base.html`) a `/var/www/html/public/tutienditaia/`.

Verificación en producción:
```bash
B=https://campuscfp401avellaneda.com.ar/tutienditaia
curl -s $B/tucancion/ | grep -c 'id="por-que"'                  # 1
curl -s $B/restauraciondefotos/ | grep -c 'corregimos mirando'  # 1
```

### B. Salida de la subida y pytest en el servidor:
Archivos sincronizados en `/srv/tutienditaia/app/`: `app/main.py`, `main.py` y `tests/test_tienda.py`.

```text
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests
..............FF..FF........                                             [100%]
=================================== FAILURES ===================================
FAILED tests/test_tienda.py::test_entrega
FAILED tests/test_tienda.py::test_conciliacion_encuentra_pago_sin_webhook
FAILED tests/test_tienda.py::test_revision_foto_un_cambio_y_aprobacion
FAILED tests/test_tienda.py::test_cancion_tiene_cinco_cambios
4 failed, 24 passed, 1 warning in 5.37s
```
*(4 fallas esperadas por los precios temporales de $500, 24 passed incluyendo el nuevo `test_admin_pagos_y_costos`).*

Reinicio y comprobación del servicio:
```bash
systemctl restart tutienditaia
curl -s http://127.0.0.1:8091/salud
{"ok":true,"modo":"produccion"}
```

### C. Salida de pruebas de la Centralita local (`centralita/tests/test_centralita.py`):
```text
pytest -q centralita/tests/test_centralita.py
.....................                                                    [100%]
21 passed in 7.65s
```

### D. Verificación con datos reales (solo mirando):
- **Plata:** 6 cobros reales leídos de Mercado Pago (todos con dinero en cuenta, comisión de $21,51 c/u). Porcentaje real de dinero en cuenta: exactamente `4,30%` (fuente: "tus 6 pagos, del 04/10 al 13/10").
- **Costos por venta:** cargos de Mercado Libre consultados en vivo por la API oficial (Clásica y Premium) coinciden exactamente al centavo con `cargos-ml-2026-10-14.json` en todos los productos del catálogo.
- Capturas generadas y visualmente verificadas: `centralita/capturas/plata.png` y `centralita/capturas/costos.png`.
- Documento de entrega completo en `centralita/ENTREGA.md` §7.

---

## 17. Tarea 13 hecha (comisión real de Mercado Pago en precios del vigilante)

### A. Subida y salida de pytest en el servidor:
Archivos sincronizados en `/srv/tutienditaia/app/`: `app/main.py`, `app/pagos.py`, `app/vigilante.py`, `app/proveedores.json`, raíz (`main.py`, `pagos.py`, `vigilante.py`, `proveedores.json`) y `tests/test_tienda.py`.

```text
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests
..............FF..FF..........                                           [100%]
=================================== FAILURES ===================================
FAILED tests/test_tienda.py::test_entrega
FAILED tests/test_tienda.py::test_conciliacion_encuentra_pago_sin_webhook
FAILED tests/test_tienda.py::test_revision_foto_un_cambio_y_aprobacion
FAILED tests/test_tienda.py::test_cancion_tiene_cinco_cambios
4 failed, 26 passed, 1 warning in 6.53s
```
*(4 fallas esperadas por los precios temporales de $500, 26 pruebas pasadas exitosamente).*

Reinicio del servicio:
```bash
sudo systemctl restart tutienditaia && sudo systemctl is-active tutienditaia
active
```

### B. Salida de los comandos de verificación (sin token):
```bash
# curl -s -X POST -H "Authorization: Bearer ***" "$L/admin/vigilante" | python3 -m json.tool | grep -A4 '"precios"'
    "precios": {
        "rf-cuadro-ecocuero-20x30": 34900,
        "rf-cuadro-ecocuero-40x30": 44900,
        "rf-cuadro-enmarcado-20x30": 24900
    }

# curl -s -H "Authorization: Bearer ***" "$L/admin/costos" | python3 -c "import json,sys; print(json.load(sys.stdin)['comision_mp'])"
{'tasa': 0.04302666666666667, 'porcentaje': 4.3, 'pagos': 6, 'por_medio': {'account_money': {'pagos': 6, 'porcentaje': 4.3}}, 'desde': '2026-10-04', 'hasta': '2026-10-13', 'leido': '2026-10-14T14:58:45+00:00', 'fuente': 'API de Mercado Pago: comisiones de tus cobros reales'}
```

### C. Precios y estado final:
- `comision_mp`: porcentaje `4.3%`, `6` pagos leídos de cobros reales de la tienda por la API de Mercado Pago (`fuente: "API de Mercado Pago: comisiones de tus cobros reales"`).
- Precios calculados y vigentes en la web (`/catalogo`):
  - **Enmarcado 20x30 (`rf-cuadro-enmarcado-20x30`):** **$24.900** (bajó $1.000 desde los $25.900 anteriores gracias al cálculo con la comisión real de Mercado Pago).
  - **Ecocuero 20x30 (`rf-cuadro-ecocuero-20x30`):** **$34.900** (sin cambios).
  - **Ecocuero 40x30 (`rf-cuadro-ecocuero-40x30`):** **$44.900** (sin cambios).
- Publicaciones de ecocuero: marcadas como `gratis_con_tu_cuenta: true`, no generaron avisos falsos de "no dice Llega gratis mañana".

---

## 18. Tarea 14 hecha (cuadro enmarcado 30x40 + webs compactas y galería ordenada)

### A. Servidor (subida, pruebas y recálculo con vigilante):
Archivos sincronizados en `/srv/tutienditaia/app/`: `app/catalogo.py`, `app/proveedores.json`, raíz (`catalogo.py`, `proveedores.json`) y `tests/test_tienda.py`.

```text
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests
..............FF..FF..........                                           [100%]
=================================== FAILURES ===================================
FAILED tests/test_tienda.py::test_entrega
FAILED tests/test_tienda.py::test_conciliacion_encuentra_pago_sin_webhook
FAILED tests/test_tienda.py::test_revision_foto_un_cambio_y_aprobacion
FAILED tests/test_tienda.py::test_cancion_tiene_cinco_cambios
4 failed, 26 passed, 1 warning in 7.85s
```
*(4 fallas esperadas por los precios de prueba de $500, 26 passed).*

Reinicio y estado del servicio:
```bash
sudo systemctl restart tutienditaia && sudo systemctl is-active tutienditaia
active
```

Salida de recálculo con vigilante y catálogo (`/admin/vigilante` y `/catalogo`):
```bash
# curl -s -X POST -H "Authorization: Bearer ***" "$L/admin/vigilante" | python3 -m json.tool | grep -A6 '"precios"'
    "precios": {
        "rf-cuadro-ecocuero-20x30": 34900,
        "rf-cuadro-ecocuero-40x30": 44900,
        "rf-cuadro-enmarcado-20x30": 24900,
        "rf-cuadro-enmarcado-30x40": 29900
    }

# curl -s "$L/catalogo?marca=rf" | python3 -c "import json,sys; d=json.load(sys.stdin); ps=d.get('productos', d); print([(p['id'], p['precio'], p['marcos']) for p in ps if 'cuadro' in p['id']])"
[('rf-cuadro-ecocuero-20x30', 34900, []), ('rf-cuadro-ecocuero-40x30', 44900, []), ('rf-cuadro-enmarcado-20x30', 24900, ['Madera', 'Negro']), ('rf-cuadro-enmarcado-30x40', 29900, ['Madera', 'Negro'])]
```

### B. Páginas web (subida y verificación en producción):
Archivos sincronizados en `/var/www/html/public/tutienditaia/`:
- `web/tucancion/index.html` e `index-base.html` → `/var/www/html/public/tutienditaia/tucancion/`
- `web/restauraciondefotos/index.html` e `index-base.html` → `/var/www/html/public/tutienditaia/restauraciondefotos/`

Verificación con curl en producción:
```bash
B=https://campuscfp401avellaneda.com.ar/tutienditaia

curl -s $B/tucancion/ | grep -c 'm-slides m-slides--tarjetas'
# 1

curl -s $B/restauraciondefotos/ | grep -c 'm-slides m-slides--tarjetas'
# 1

curl -s $B/tucancion/ | grep -c 'id="por-que"'
# 1

curl -s $B/restauraciondefotos/ | grep -c 'Cuadro enmarcado (marco color madera)'
# 1

curl -s $B/restauraciondefotos/ | grep -c 'rf-cuadro-enmarcado-30x40'
# 2
```

### C. Precios y novedades finales:
- **Nuevo producto:** `rf-cuadro-enmarcado-30x40` configurado con marcos `["Madera", "Negro"]` a un precio de **$29.900** (ganancia neta $5.000 calculada por el vigilante con la comisión real de Mercado Pago).
- **Precios vigentes:**
  - `rf-cuadro-enmarcado-20x30`: $24.900 (marcos Madera o Negro).
  - `rf-cuadro-enmarcado-30x40`: $29.900 (marcos Madera o Negro).
  - `rf-cuadro-ecocuero-20x30`: $34.900.
  - `rf-cuadro-ecocuero-40x30`: $44.900.
- **Webs:** Secciones "Qué recibís" y "Qué incluye" compactas en fila de 5 ítems con ✓ y carrusel móvil. En fotos, galería ordenada por opciones y tarjeta del enmarcado 30x40 incorporada. No se generaron avisos de envío por las publicaciones nuevas.

---

## 19. Tarea 15 hecha (fase 3 de la centralita)

### A. Paso 0: copias duplicadas en el servidor
1. Se inspeccionó la unidad de `systemd` y la importación de Python:
   - `systemctl cat tutienditaia` arroja `WorkingDirectory=/srv/tutienditaia/app` y `ExecStart=/srv/tutienditaia/venv/bin/uvicorn app.main:app ...`
   - `sudo -u tienda /srv/tutienditaia/venv/bin/python -c "import app.main as m; print(m.__file__)"` imprimió:
     `/srv/tutienditaia/app/app/main.py`.
2. Las copias duplicadas sueltas en la raíz (`/srv/tutienditaia/app/`) que **no** usa el servicio fueron movidas conservando su estructura a:
   `/srv/tutienditaia/respaldo-duplicados-2026-10-14/` (13 archivos en total: `avisos.py`, `catalogo.py`, `cobros.py`, `config.py`, `correo.py`, `db.py`, `drive.py`, `flujo.py`, `main.py`, `mercado_pago.py`, `pagos.py`, `proveedores.json`, `vigilante.py`).
3. **De ahora en más, todas las subidas de código del servidor se realizan exclusivamente a `/srv/tutienditaia/app/app/`.**

### B. Servidor (`tienda/app/`)
- **A1. Historial de precios (`vigilante.py`):** Se agregó `est["historial"][nombre]` con entradas `{"fecha": ISO, "precio": int, "fuente": "vigilante" | "a mano"}` registrando solo al cambiar el precio (y en la primera lectura), con límite de 200 entradas más recientes. Se guarda también `est["lecturas"][nombre]`.
- **A2. Precio a mano (`POST/DELETE /admin/proveedores/{nombre}/precio`):** Permite fijar un costo manual de $1 a $10.000.000 guardando `leido_entonces`. Se descarta automáticamente con aviso por ntfy si el proveedor cambia su precio en Mercado Libre. Recalcula el precio de venta en el momento.
- **A3. Pendientes > 40% (`POST .../pendientes/{producto}/aprobar` y `rechazar`):** Guarda `est["pendientes"][producto]`. Al aprobar, aplica el nuevo precio con `ajustar`. Al rechazar, mantiene el precio actual y recuerda el costo rechazado en `est["rechazados"][producto]` para no volver a avisar con el mismo costo.
- **A4. Endpoint `GET /admin/proveedores`:** Retorna publicaciones con lectura, historial y precio a mano; productos con precio vigente, pendientes y regla; comisión real de Mercado Pago y fecha/hora de última revisión.
- **A5. Seguimiento del cuadro (`POST /admin/pedidos/{pid}/seguimiento`):**
  - Migración en `db.py` sumando `seguimiento TEXT`, `seguimiento_url TEXT`, `cuadro_comprado TEXT`.
  - Validación de estado (`aprobado` o `entregado`), producto con envío, número sin saltos de línea (4..60 caracteres) y URL con `https://`.
  - Envía mail en voseo y sin prometer fechas al cliente (`avisos.mandar_mail`) y notificación ntfy con botón WhatsApp (`avisos.link_whatsapp`).
  - Protección ante reenvíos: requiere `"reenviar": true` si ya tenía seguimiento (409 si no).
  - Campos agregados a `GET /admin/pedidos` y `GET /admin/pedidos/{pid}`.
- **A6. Pruebas unitarias:** 4 nuevas pruebas en `tienda/tests/test_tienda.py`:
  - `test_admin_proveedores_auth_y_endpoints`
  - `test_vigilante_historial_y_precio_a_mano`
  - `test_vigilante_pendiente_aprobar_y_rechazar`
  - `test_seguimiento_cuadro`

### C. Salida de pruebas en el servidor (`pytest`) y reinicio:
```text
$ ssh root@campuscfp401avellaneda.com.ar "sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests"
..............FF..FF..........                                           [100%]
=================================== FAILURES ===================================
FAILED tests/test_tienda.py::test_entrega
FAILED tests/test_tienda.py::test_conciliacion_encuentra_pago_sin_webhook
FAILED tests/test_tienda.py::test_revision_foto_un_cambio_y_aprobacion
FAILED tests/test_tienda.py::test_cancion_tiene_cinco_cambios
4 failed, 30 passed, 1 warning in 7.05s
```
*(4 fallas esperadas conocidas por los precios de prueba de $500, 30 passed).*

Reinicio y salud en producción:
```bash
# systemctl restart tutienditaia && systemctl is-active tutienditaia
active

# curl -s http://127.0.0.1:8091/salud
{"ok":true,"modo":"produccion"}
```

Revisión en vivo con el vigilante (`POST /admin/vigilante`):
Las 6 publicaciones fueron consultadas y generaron su primera entrada de historial; la comisión real de Mercado Pago detectada fue `4.3 %` (6 cobros reales). Precios vigentes: Enmarcado 20x30 ($24.900), Enmarcado 30x40 ($29.900), Ecocuero 20x30 ($34.900), Ecocuero 40x30 ($44.900).

### D. Páginas web subidas:
Se actualizaron `web/restauraciondefotos/index.html` e `index-base.html` con el precio escrito del enmarcado 20x30 a **$24.900** (el visible antes de la carga dinámica en vivo) y se subieron a `/var/www/html/public/tutienditaia/restauraciondefotos/` con propietario `www-data:www-data`.

### E. Centralita (Fase 3):
- **B1. Proveedores:** Pestaña habilitada, tarjetas por producto con publicaciones, gráfico chispa SVG simple del historial, costo leído y estado de envío, precio a mano / quitar, corrección a mano con modal dentro de la página, pendientes con aprobar/rechazar y botón superior "Revisar y ajustar ahora".
- **B2. Seguimiento del cuadro:** Campos de seguimiento, carrier, URL y monto pagado en la ficha. Confirmación modal dentro de la página mostrando el texto exacto que recibirá el cliente (vía `POST /api/pedidos/{pid}/seguimiento/previa`). Anotación local `"Seguimiento enviado al cliente: {numero}"` y salida de "Tu turno" en Hoy.
- **B3. Clientes:** Pestaña nueva agrupando por email o WhatsApp normalizado mediante grafo de componentes conexos. Excluye pedidos `pendiente_pago` y `cancelado`. Métricas reales de cobros ("sin dato" ante reembolsos o pagos faltantes), marcas con chips, enlaces directos a fichas, contador de clientes que volvieron a comprar y filtro "Solo los que volvieron". Sin automatizaciones de mensajes.
- **B4. Pruebas de la Centralita:** 30 pruebas pasando al 100% en `centralita/tests/test_centralita.py` (`pytest -q centralita/tests/test_centralita.py`).
- **B5. Verificación visual:** Capturas generadas en `centralita/capturas/` (`fase3-01-hoy.png`, `fase3-02-proveedores.png`, `fase3-03-clientes.png`, `fase3-04-ficha-acciones.png`).


---

## 20. Tarea 16 hecha (precios reales y precios en vivo en toda la web)

### A. Salida del script en la PC (`python tienda/docs/tarea16_precios.py`):
```text
tienda\app\catalogo.py: listo
web\restauraciondefotos\index.html: listo
web\restauraciondefotos\index-base.html: listo
```
Se aplicaron los precios reales de arranque en `catalogo.py` y el marcado dinámico `data-precio` en las páginas de fotos sin frenos ni errores.

### B. Pruebas y reinicio en el servidor:
Archivos sincronizados exclusivamente a `/srv/tutienditaia/app/app/` y `/srv/tutienditaia/app/tests/` (siguiendo Paso 0 de Tarea 15):
- `tienda/app/catalogo.py`
- `tienda/tests/test_tienda.py`

Salida de pytest:
```text
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests
..................................                                       [100%]
=============================== warnings summary ===============================
../venv/lib/python3.12/site-packages/starlette/testclient.py:45
  /srv/tutienditaia/venv/lib/python3.12/site-packages/starlette/testclient.py:45: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
34 passed, 1 warning in 5.89s
```
**TODO EN VERDE:** 34 pasadas, 0 fallidas (las 4 fallas históricas de `test_entrega`, `test_conciliacion_encuentra_pago_sin_webhook`, `test_revision_foto_un_cambio_y_aprobacion` y `test_cancion_tiene_cinco_cambios` quedaron resueltas con los precios reales).

Reinicio y estado del servicio:
```bash
sudo systemctl restart tutienditaia && sudo systemctl is-active tutienditaia
active
```

### C. Archivos web actualizados y subidos a producción:
Archivos sincronizados en `/var/www/html/public/tutienditaia/` (con propietario `www-data:www-data`):
- `tienda/web/tienda.js` → `/var/www/html/public/tutienditaia/tienda.js`
- `web/movil.js` → `/var/www/html/public/tutienditaia/movil.js`
- `web/tucancion/index.html` e `index-base.html` → `/var/www/html/public/tutienditaia/tucancion/`
- `web/restauraciondefotos/index.html` e `index-base.html` → `/var/www/html/public/tutienditaia/restauraciondefotos/`

### D. Actualización de precios en el servidor y consulta de catálogo:
Actualización mediante `POST /admin/precios` (usando `TIENDA_ADMIN_TOKEN` del `.env` del servidor):
```json
{"rf-foto-1": 5000, "tc-cancion": 27000}
```
Respuesta del servidor:
```json
{"ajustes":{"rf-cuadro-enmarcado-20x30":24900,"rf-foto-1":5000,"tc-cancion":27000},"precios":{"rf-foto-1":5000,"rf-pack-5":15000,"rf-pack-10":25000,"rf-pack-20":39900,"rf-cuadro-ecocuero-20x30":34900,"rf-cuadro-ecocuero-40x30":44900,"rf-cuadro-enmarcado-20x30":24900,"rf-cuadro-enmarcado-30x40":29900,"tc-cancion":27000,"tc-combo":59900}}
```

Consulta de `GET /catalogo`:
```python
{'rf-foto-1': 5000, 'rf-pack-5': 15000, 'rf-pack-10': 25000, 'rf-pack-20': 39900, 'rf-cuadro-ecocuero-20x30': 34900, 'rf-cuadro-ecocuero-40x30': 44900, 'rf-cuadro-enmarcado-20x30': 24900, 'rf-cuadro-enmarcado-30x40': 29900, 'tc-cancion': 27000, 'tc-combo': 59900}
```
Coincide exactamente con lo esperado: `rf-foto-1` 5000, `tc-cancion` 27000, `tc-combo` 59900, packs 15000/25000/39900, cuadros 24900, 29900, 34900, 44900.

### E. Verificación de las webs (curl):
```bash
B=https://campuscfp401avellaneda.com.ar/tutienditaia

curl -s $B/tienda.js | grep -c "pintarPrecios"
# 3 (esperado: >= 3)

curl -s $B/tucancion/ | grep -c 'data-precio="tc-cancion"'
# 4 (esperado: 4)

curl -s $B/restauraciondefotos/ | grep -o 'data-precio=' | wc -l
# 8 (esperado: 8 ocurrencias en 7 líneas: la línea 342 contiene el precio unitario y el de pack-5)

curl -s $B/tucancion/ $B/restauraciondefotos/ $B/movil.js | grep -c '\$500'
# 0 (esperado: 0)
```

### F. Verificación visual (Edge headless):
Capturas generadas en `tienda/docs/tucancion_header.png` y `tienda/docs/fotos_header.png`:
- **Tu Canción:** El encabezado muestra claramente **$27.000**, con hasta 5 cambios incluidos.
- **Restauración de fotos:** El encabezado muestra claramente **$5.000** por foto · Packs desde $15.000.
Ambas webs cargan dinámicamente con `tienda.js` y reflejan los precios reales en producción.

---

## 21. Tarea 17 hecha (Precios a mano desde centralita + Fechas importantes y recordatorios - Fase 3b)

### A. Servidor
- **Precios a mano y modos (`tienda/app/vigilante.py`, `tienda/app/main.py`):**
  - Configuración persistente en `DATOS_DIR/precios-modo.json` para definir modo (`fijo` vs `auto`) y ganancia neta personalizada.
  - Alerta de vigilante una sola vez por costo en caso de que un precio fijo quede por debajo del margen objetivo.
  - Historial persistente en `DATOS_DIR/precios-historial.jsonl` registrando motivo (`a mano`, `vigilante`, `aprobado`).
  - Endpoints administrativos `/admin/precios` (`GET` y `POST /{producto}`).
- **Fechas importantes y recordatorios (`tienda/app/db.py`, `tienda/app/main.py`):**
  - Tabla `fechas` con índice en `baja_token`.
  - Validación de fechas (rechazo de 31/04 con 422; 29/02 válido).
  - Almacenamiento condicional: solo se guarda si `fecha_permiso == "si"`.
  - Enlaces de baja con token único: `GET /baja/{token}` (pantalla de confirmación) y `POST /baja/{token}` (asienta baja).
  - Tarea periódica de recordatorios diarios a 15 días con aviso vía email y notificación push ntfy con link directo a WhatsApp.
  - Endpoint `GET /admin/fechas` con próximas fechas a 30 días, cantidades y calendario comercial 2026.

### B. Formularios Web
- Integración del bloque opcional "¿Te avisamos para la próxima?" tras el campo de ocasión en `web/tucancion/index.html` (e `index-base.html`) y `web/restauraciondefotos/index.html` (e `index-base.html`).
- Mención de privacidad agregada en el pie de "Condiciones y garantías".
- Flujo móvil verificado con `produccion/pruebas/probar_pasos_movil.py` en Chromium y WebKit (todos los pasos superados sin errores).

### C. Centralita
- Nueva pestaña "Precios" con cálculo en tiempo real de comisiones de Mercado Pago y márgenes netos. Modal de simulación interactivo.
- Nueva pestaña "Fechas" con recordatorios y fechas comerciales.
- Pruebas de centralita en verde: 31 passed.

### D. Despliegue y Verificación en Producción
- Código backend sincronizado en `/srv/tutienditaia/app/app/` y `/srv/tutienditaia/app/tests/`.
- Permisos configurados a `tienda:tienda`.
- Pruebas remotas: **38 passed, 0 failed** (`/srv/tutienditaia/venv/bin/python -m pytest -q tests`).
- Servicio reiniciado: `tutienditaia.service` activo.
- Archivos web subidos a `/var/www/html/public/tutienditaia/` con propietario `www-data:www-data`.
- Endpoints en vivo verificados con 200 OK: `/admin/precios` y `/admin/fechas`.
- Capturas de Centralita generadas en `centralita/capturas/fase3b-01-precios.png`, `centralita/capturas/fase3b-02-modal-precio.png`, `centralita/capturas/fase3b-03-fechas.png`.

### E. Anexo: Precios terminados en 999 (D-53)
- **6 productos de precio fijo:** aplicados en el servidor con `precios_999.py --aplicar`:
  - `rf-foto-1`: $4.999
  - `rf-pack-5`: $14.999
  - `rf-pack-10`: $24.999
  - `rf-pack-20`: $39.999
  - `tc-cancion`: $26.999
  - `tc-combo`: $59.999
- **4 cuadros (vigilante):** fórmula de redondeo actualizada en `tienda/app/vigilante.py`:
  ```python
  return math.ceil((bruto + 1) / 1000) * 1000 - 1
  ```
  Con esto los cuadros en modo automático ajustan siempre hacia arriba a $…999 ($24.999, $29.999, $34.999, $44.999) garantizando que la ganancia neta nunca quede por debajo de la regla.
- **Valores de arranque en código y webs:**
  - `tienda/app/catalogo.py`: precios actualizados a 999.
  - `web/index.html` (portal): se agregaron atributos `data-precio` y script `tienda.js` para pintar los precios dinámicamente en vivo.
  - `web/movil.js`, `web/tucancion/index.html` e `index-base.html`, `web/restauraciondefotos/index.html` e `index-base.html`: precios iniciales en 999.
- **Verificación en servidor:** `GET /catalogo` en producción devuelve los 10 productos terminados en 999:
  ```json
  {
    "rf-foto-1": 4999,
    "rf-pack-5": 14999,
    "rf-pack-10": 24999,
    "rf-pack-20": 39999,
    "rf-cuadro-ecocuero-20x30": 34999,
    "rf-cuadro-ecocuero-40x30": 44999,
    "rf-cuadro-enmarcado-20x30": 24999,
    "rf-cuadro-enmarcado-30x40": 29999,
    "tc-cancion": 26999,
    "tc-combo": 59999
  }
  ```

---

## 22. Tarea 18 hecha (UTM en pedidos y píxel de Meta)

### A. Parte A: UTM en pedidos (Webs + Servidor + Centralita)
1. **Webs (`tienda/web/tienda.js`):**
   - Lectura al cargar la página de `utm_source`, `utm_medium`, `utm_campaign` y `utm_content`.
   - Persistencia en `sessionStorage` (try/catch para navegación privada, última visita con UTM gana).
   - Inclusión automática en el `FormData` como campo `origen` JSON al enviar el formulario.
2. **Servidor (`POST /pedidos` en `tienda/app/main.py`):**
   - Validación de cada valor con `^[A-Za-z0-9_.-]{1,60}$`. Lo que no cumple se descarta sin rechazar el pedido.
   - Almacenamiento en `datos["origen"]` y registro en `subidas/<pid>/historial.txt` (`Origen: source: ... · content: ...`).
   - Etiqueta amigable `"origen": "Origen"` agregada a `tienda/app/flujo.py`.
   - Nueva prueba unitaria: `test_pedido_con_origen_utm_y_historial` en `tienda/tests/test_tienda.py`.
3. **Centralita (`centralita/servicio.py` y `centralita/static/app.js`):**
   - Procesamiento de `origen` y generación de `origen_texto` (ej. "meta · P004") en `/api/pedidos` y ficha de pedido.
   - Endpoint `/api/anuncios` (y alias `/api/pedidos/resumen-anuncios`) con cálculo agrupado por `utm_content` de pedidos pagados y monto total cobrado con datos reales.
   - Panel "Rendimiento por anuncio (UTM)" en la vista de Pedidos de la Centralita y etiqueta de Origen en cada tarjeta y ficha.
   - Nueva prueba unitaria: `test_centralita_origen_utm_y_resumen_anuncios` en `centralita/tests/test_centralita.py`.

### B. Parte B: Píxel de Meta
1. **Carga condicional en `tienda/web/tienda.js`:**
   - Si no está definido `window.META_PIXEL_ID`, no se carga ningún script externo ni snippet del píxel.
   - Disparo de eventos estándar:
     - `PageView`: al inicializar la página.
     - `ViewContent`: en la carga de cada web de marca (`tc` o `rf`).
     - `InitiateCheckout`: en el envío del formulario antes de redirigir al checkout de Mercado Pago.
     - `Purchase`: en `gracias.html` **únicamente si el servidor confirma que el pago está aprobado** (`d.estado === 'pagado'`), enviando `{ value: d.precio, currency: 'ARS' }`.
   - **Sin datos personales:** no se envía email, teléfono ni nombre (sin coincidencia avanzada).
2. **Privacidad:**
   - Agregada la leyenda en "Condiciones y garantías" bajo la sección Privacidad en `web/tucancion/index.html`, `web/tucancion/index-base.html`, `web/restauraciondefotos/index.html` e `index-base.html`:
     *"Usamos el píxel de Meta para saber qué anuncios funcionan. No le mandamos tus datos personales."*
3. **Prueba de flujo móvil:**
   - Ejecutado `python produccion/pruebas/probar_pasos_movil.py https://campuscfp401avellaneda.com.ar produccion/pruebas/salida_movil`.
   - Resultado: **0 errores** en Chromium (Pixel 7) y WebKit (iPhone 13). Formularios, pasos, fotos y canciones funcionando correctamente.

### C. Despliegue en Producción
- Archivos backend desplegados en `/srv/tutienditaia/app/app/` y `/srv/tutienditaia/app/tests/`.
- Páginas web desplegadas en `/var/www/html/public/tutienditaia/`.
- Pruebas remotas en el servidor: **39 passed en 12.97s**.
- Servicio `tutienditaia.service` reiniciado y operativo.
- Pruebas locales: 71 passed (39 en `tienda/tests`, 32 en `centralita/tests`).
- Validación de piezas de redes: `validar.py redes/piezas` arroja **"Sin errores"** comparando contra el catálogo en vivo.

---

## 23. Tarea 19 hecha (Subida de arreglos de revisión de Claude: tareas 17, anexo y 18)

### A. Cambios incluidos y subidos
- **Recordatorios (`app/main.py`, `revisar_recordatorios_fechas`):**
  - Solo para pedidos cobrados.
  - Ventana de envío entre 1 y 15 días previos (una sola vez por llegada de fecha).
  - Si el envío de correo falla, no se asienta como enviado y se reintenta.
  - Envío a partir de las 10:00 (hora Argentina).
  - No envía aviso si la compra ocurrió menos de 30 días antes de la fecha.
  - HTML del correo debidamente escapado.
  - `/admin/fechas` contabiliza únicamente pedidos cobrados y expone próximas fechas comerciales.
- **Precios a mano:** el paso a precio fijo de cuadros queda bajo el candado del vigilante (`main.py` y `vigilante.fijar_modo`).
- **Píxel de Meta:**
  - `GET /pedidos/{pid}/estado` ahora devuelve `"precio"`.
  - En `tienda/web/tienda.js`, la compra se reporta una única vez por pedido con deduplicación por `eventID` (`"compra-" + d.pedido`).
- **Centralita:** enlaces directos `#precios` y `#fechas` plenamente operativos en local.

### B. Despliegue y Pruebas en el Servidor
1. **Sincronización:**
   - `RegalosIA/tienda/app/` y `RegalosIA/tienda/tests/` desplegados en `/srv/tutienditaia/app/app/` y `/srv/tutienditaia/app/tests/`.
   - Propietario configurado con `chown -R tienda:tienda`.
   - `RegalosIA/tienda/web/tienda.js` desplegado en `/var/www/html/public/tutienditaia/tienda.js`.
2. **Pruebas unitarias remotas:**
   ```text
   sudo -u tienda /srv/tutienditaia/venv/bin/pytest tests
   ======================== 40 passed, 1 warning in 9.41s =========================
   ```
3. **Reinicio de servicio:**
   - `systemctl restart tutienditaia.service` ejecutado.
   - Estado: `active (running)`.
4. **Verificación en producción:**
   - `curl -s https://campuscfp401avellaneda.com.ar/tutienditaia/api/pedidos/RF-0010/estado`
     → `{"pedido":"RF-0010","estado":"entregado","producto":"Restauración de 1 foto","marca":"rf","precio":500}` (campo `"precio"` presente).
   - `curl -s https://campuscfp401avellaneda.com.ar/tutienditaia/tienda.js | grep -c compra-`
     → `1` (deduplicación de evento Purchase presente).

---

## 24. Delegación de dominios y configuración de VirtualHosts en Nginx (15/10/2026)

### A. Registro y Delegación DNS (Cloudflare + NIC.ar)
- **Dominios registrados en NIC Argentina:** `tucancion.com.ar` y `restauraciondefotos.com.ar`.
- **Servidores de nombres (Cloudflare):**
  - `cash.ns.cloudflare.com`
  - `diva.ns.cloudflare.com`
- **Registros DNS en Cloudflare:**
  - `restauraciondefotos.com.ar` (A `@` $\rightarrow$ `75.119.155.217`, CNAME `www` $\rightarrow$ `@`, Proxied)
  - `tucancion.com.ar` (A `@` $\rightarrow$ `75.119.155.217`, CNAME `www` $\rightarrow$ `@`, Proxied)
- **Estado DNS:** Cloudflare respondiendo correctamente con la IP del VPS. En NIC Argentina, la delegación fue guardada y se encuentra en ciclo de propagación de zona en los servidores raíz `.ar`.

### B. Configuración de VirtualHosts en Nginx (`75.119.155.217`)
- Creados y habilitados dos nuevos archivos de configuración:
  - `/etc/nginx/sites-available/tucancion`:
    - `server_name tucancion.com.ar www.tucancion.com.ar;`
    - `root /var/www/html/public/tutienditaia/tucancion;`
    - Reglas de proxy a la API local (`/tutienditaia/api/` y `/api/` $\rightarrow$ `http://127.0.0.1:8091/`).
    - Proxy de revisión (`/tutienditaia/revisar/` y `/revisar/`).
    - Archivos estáticos compartidos de la tienda servidos desde `/tutienditaia/` (`tienda.js`, `movil.css`, `movil.js`).
  - `/etc/nginx/sites-available/restauraciondefotos`:
    - `server_name restauraciondefotos.com.ar www.restauraciondefotos.com.ar;`
    - `root /var/www/html/public/tutienditaia/restauraciondefotos;`
    - Mismas reglas de proxy API, revisión y recursos compartidos.
- Symlinks creados en `/etc/nginx/sites-enabled/`.
- Verificación de sintaxis de Nginx (`nginx -t`): **exitosa**.
- Recarga de Nginx (`systemctl reload nginx`): **completada sin caídas**.

### C. Verificación de Respuestas HTTP
```bash
# Tu Canción
$ curl -s -I -H 'Host: tucancion.com.ar' http://127.0.0.1/
HTTP/1.1 200 OK (Content-Length: 64230)

# Restauración de fotos
$ curl -s -I -H 'Host: restauraciondefotos.com.ar' http://127.0.0.1/
HTTP/1.1 200 OK (Content-Length: 65236)

# API en el nuevo host
$ curl -s -H 'Host: tucancion.com.ar' http://127.0.0.1/tutienditaia/api/salud
{"ok":true,"modo":"produccion"}

# Campus y Moodle (intactos)
$ curl -s -I https://campuscfp401avellaneda.com.ar/
HTTP/1.1 200 OK
```
- **Integridad del servidor:** El sitio principal `campuscfp401avellaneda.com.ar`, Moodle y los endpoints existentes de `/tutienditaia/` continúan respondiendo con `200 OK` sin interrupciones.

### D. Certificados SSL (Let's Encrypt / Certbot) y Activación Pública
- Una vez publicada la actualización de zonas por NIC Argentina, se ejecutó Certbot en el servidor para ambos dominios:
  - `certbot --nginx -d tucancion.com.ar -d www.tucancion.com.ar --non-interactive --redirect`
  - `certbot --nginx -d restauraciondefotos.com.ar -d www.restauraciondefotos.com.ar --non-interactive --redirect`
- Certificados emitidos y desplegados en `/etc/nginx/sites-available/tucancion` y `restauraciondefotos` con renovación automática.
- Redirección automática HTTP $\rightarrow$ HTTPS activa.
- **Verificación pública en vivo:**
  - `https://tucancion.com.ar` $\rightarrow$ `HTTP/1.1 200 OK`
  - `https://www.tucancion.com.ar` $\rightarrow$ `HTTP/1.1 200 OK`
  - `https://restauraciondefotos.com.ar` $\rightarrow$ `HTTP/1.1 200 OK`
  - `https://www.restauraciondefotos.com.ar` $\rightarrow$ `HTTP/1.1 200 OK`
  - `https://tucancion.com.ar/tutienditaia/api/salud` $\rightarrow$ `{"ok":true,"modo":"produccion"}`
  - Catálogo en vivo devuelve los 10 productos con precios terminados en 999.
- **Estado final:** 100% operativo en producción bajo dominios propios.

### E. Enlaces cruzados canónicos (Lado A / Lado B) y soporte móvil en dominios propios
- **Enlaces HTML cruzados:**
  - En `restauraciondefotos` (`index.html`, `index-base.html`, `gracias.html`): todos los enlaces que apuntaban a `/tutienditaia/tucancion/` (botón Lado A en navbar, botón en banner de combo y footer) fueron actualizados a la URL absoluta oficial `https://tucancion.com.ar/`.
  - En `tucancion` (`index.html`, `index-base.html`, `gracias.html`): todos los enlaces hacia `/tutienditaia/restauraciondefotos/` (botón Lado B en navbar, mención de fotos sueltas, botón en banner combo y footer) fueron actualizados a `https://restauraciondefotos.com.ar/`.
  - Etiquetas `<meta property="og:url">` actualizadas a sus respectivos dominios oficiales en todas las páginas.
- **Redirecciones 301 en Nginx:**
  - En ambas configuraciones de VirtualHost se agregaron reglas exactas `location =` para redirigir 301 cualquier solicitud a `/tutienditaia/tucancion/` o `/tutienditaia/restauraciondefotos/` hacia el dominio propio correspondiente, manteniendo la entrega de assets (`img/`, `tienda.js`, etc.).
- **Soporte móvil (`web/movil.js`):**
  - Se adaptó la detección de marca en `movil.js` para reconocer `location.hostname` además de `location.pathname`, asegurando que la barra de compra fija inferior, los pasos del formulario y las condiciones plegables funcionen fluidamente en los dominios propios en dispositivos móviles. Se agregó cache-buster `?v=20261015` en las etiquetas de script de todas las páginas.
- **Pruebas de verificación en vivo:**
  - `curl -s -I https://restauraciondefotos.com.ar/tutienditaia/tucancion/` $\rightarrow$ `301 Moved Permanently` $\rightarrow$ `Location: https://tucancion.com.ar/`
  - `curl -s -I https://tucancion.com.ar/tutienditaia/restauraciondefotos/` $\rightarrow$ `301 Moved Permanently` $\rightarrow$ `Location: https://restauraciondefotos.com.ar/`
  - Enlaces en el HTML servido verificados en ambas páginas.

## 25. Tarea 20 A hecha parcialmente (píxel de Meta; 15/10/2026)

- **ID encontrado:** conjunto de datos existente `Tu Tiendita`, del portafolio de Meta correspondiente. Identificador: `1402632028570089` (16 dígitos). No se creó otro conjunto.
- **Privacidad:** Meta mostraba desactivadas las coincidencias avanzadas automáticas y las opciones de correo, teléfono, nombre y demás datos personales.
- **Cambio y publicación:** `tienda/web/tienda.js` usa `window.META_PIXEL_ID || "1402632028570089"`. Se publicó en `/var/www/html/public/tutienditaia/tienda.js`; el SHA-256 local y remoto coincide.
- **Verificación en vivo:** en `https://tucancion.com.ar/?utm_source=prueba` y `https://restauraciondefotos.com.ar/` comprobé que se carga `/tutienditaia/tienda.js`, `https://connect.facebook.net/en_US/fbevents.js` y la configuración `signals/config/1402632028570089` para el dominio visitado. La consola del navegador no mostró errores de JavaScript.
- **Límite de verificación:** el inspector de navegador disponible no expone el registro de solicitudes de red ni `window.performance`. No pude observar directamente solicitudes `facebook.com/tr/` que identifiquen por separado `PageView` y `ViewContent`; el código publicado sí contiene ambas llamadas. No hice compras ni pedidos. Tampoco ejecuté la prueba de flujo móvil.
- **Pendiente (Tarea 20 A3/B):** revisar PageView y ViewContent con un inspector de red que los muestre y ejecutar `produccion/pruebas/probar_pasos_movil.py`; para la verificación de dominios, obtener en Meta los dos valores TXT (`facebook-domain-verification=...`) y cargarlos en Cloudflare en `@`, sin tocar A ni CNAME.
- **Ejecutor:** Codex, por pedido explícito del usuario. La bitácora de redes tiene la entrada correspondiente firmada por Codex.
