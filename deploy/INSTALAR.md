# Instalar la tienda en el servidor (para Antigravity)

El servidor del campus es de Nicolás y aloja Moodle y el campus del secundario, con **datos reales de alumnos**. La tienda va **aislada**: usuario de Linux propio, carpeta propia, servicio propio y claves propias. No toca la base de Moodle, ni el `.env` del campus, ni sus usuarios.

## 1. Usuario y carpetas
```bash
sudo adduser --system --group --home /srv/tutienditaia --shell /usr/sbin/nologin tienda
sudo mkdir -p /srv/tutienditaia/{app,datos,secretos}
sudo chown -R tienda:tienda /srv/tutienditaia
sudo chmod 700 /srv/tutienditaia/datos /srv/tutienditaia/secretos
```

## 2. Código y entorno
Copiá `RegalosIA/tienda/app/`, `requirements.txt` y `tests/` a `/srv/tutienditaia/app/` (quedan `/srv/tutienditaia/app/app/main.py`, etc.).
```bash
cd /srv/tutienditaia/app
sudo -u tienda python3 -m venv /srv/tutienditaia/venv
sudo -u tienda /srv/tutienditaia/venv/bin/pip install -r requirements.txt
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests   # tienen que pasar 16
```

## 3. Claves (las pasa Nicolás desde `claves-tienda.txt`; nunca van al repo ni al chat)
`/srv/tutienditaia/.env` (dueño `tienda`, permisos 600). Copiá **todas** las líneas de `claves-tienda.txt` y agregá:
```
MP_MODO=produccion
URL_PUBLICA=https://campuscfp401avellaneda.com.ar
RUTA_API=/tutienditaia/api
DATOS_DIR=/srv/tutienditaia/datos
DRIVE_TOKEN_ARCHIVO=/srv/tutienditaia/secretos/drive_token.json
```
Copiá `drive_token.json` a `/srv/tutienditaia/secretos/` (dueño `tienda`, 600).
**Importante:** `claves-tienda.txt` viene de Windows. Después de armar el `.env`, corré `sudo sed -i 's/\r$//' /srv/tutienditaia/.env` (systemd no saca el retorno de carro de fin de línea y rompe los tokens).
$//' /srv/tutienditaia/.env` (systemd no saca el `
` y rompe los tokens).
```bash
sudo chown tienda:tienda /srv/tutienditaia/.env /srv/tutienditaia/secretos/drive_token.json
sudo chmod 600 /srv/tutienditaia/.env /srv/tutienditaia/secretos/drive_token.json
```
Para la primera compra de prueba se puede usar `MP_MODO=prueba` (credenciales de prueba) y después cambiar a `produccion` y reiniciar.

## 4. Servicio
Copiá `deploy/tutienditaia.service` a `/etc/systemd/system/` y:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tutienditaia
curl -s http://127.0.0.1:8091/salud        # {"ok":true,"modo":"produccion"}
```

## 5. Nginx (dentro del `server` de campuscfp401avellaneda.com.ar con HTTPS, hoy en `sites-available/moodle`)
Pegá el contenido de `deploy/nginx-tutienditaia.conf` **antes** de cualquier `location ~ …` de Moodle. Los `^~` hacen que estas rutas no las tomen las reglas de PHP o de caché de Moodle.
```bash
sudo nginx -t && sudo systemctl reload nginx
curl -s https://campuscfp401avellaneda.com.ar/tutienditaia/api/salud
```

## 6. Webs
- `/var/www/html/public/tutienditaia/tienda.js` ← `RegalosIA/tienda/web/tienda.js` (sin cambios)
- `/var/www/html/public/tutienditaia/tucancion/` ← web de Tu Canción (`index.html`, `gracias.html`, `img/`…)
- `/var/www/html/public/tutienditaia/restauraciondefotos/` ← web de Restauración de fotos
- `/var/www/html/public/tutienditaia/index.html` ← portada simple con las dos tiendas (es la URL que figura en Mercado Pago)

## 7. Verificación
1. `https://…/tutienditaia/api/catalogo` devuelve los 9 productos.
2. Pedido de prueba desde la web, que llegue a Mercado Pago, y `journalctl -u tutienditaia -f` sin errores.
3. Al pagar, `gracias.html` pasa a "¡Listo!", llega el mail, la carpeta aparece en Drive y llega la notificación de ntfy.

## Mantenimiento
- Logs: `journalctl -u tutienditaia`.
- Datos: `/srv/tutienditaia/datos/tienda.db` (SQLite) y `subidas/` (fotos de pedidos sin pagar, que se borran solas a los 3 días). Hacé backup de `tienda.db`.
- Actualizar: copiar `app/`, correr los tests y `sudo systemctl restart tutienditaia`. Con `restart`, no con `reload`.
