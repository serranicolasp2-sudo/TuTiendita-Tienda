# Tarea 2 para Antigravity: versión móvil + link de revisión (Nginx)

Proyecto `C:\Users\Nicolás\Desktop\Proyectos\RegalosIA`. Claude ya hizo y probó los cambios; **no los modifiques**, solo subilos y verificá. Si algo no funciona, anotalo en `tienda/docs/ENTREGA-ANTIGRAVITY.md` y no lo arregles por tu cuenta.

## 1. Versión móvil de las webs (ya hecha por Claude)
Archivos nuevos en `web/`:
- `web/movil.css`: solo actúa hasta 640 px de ancho.
- `web/movil.js`: en celular agrega la barra fija "Pedir ahora", pliega condiciones y preguntas frecuentes y muestra la pista "Deslizá…".

Cambios en `web/tucancion/` y `web/restauraciondefotos/`: `index.html`, `index-base.html` y `gracias.html` ahora cargan esos archivos en el `<head>`. No cambió nada más.

Subí al servidor:
- `web/movil.css` → `/var/www/html/public/tutienditaia/movil.css`
- `web/movil.js` → `/var/www/html/public/tutienditaia/movil.js`
- `web/tucancion/index.html`, `index-base.html`, `gracias.html` → `/var/www/html/public/tutienditaia/tucancion/`
- `web/restauraciondefotos/index.html`, `index-base.html`, `gracias.html` → `/var/www/html/public/tutienditaia/restauraciondefotos/`

### Muestras reales (también hechas por Claude)
- **Restauración de fotos:** el hero de `index.html` e `index-base.html` ahora tiene un comparador deslizable de antes y después, en lugar de los recuadros "[foto original]" y "[foto restaurada]". Subí `web/restauraciondefotos/img/muestra-antes.jpg` y `muestra-despues.jpg` a `/var/www/html/public/tutienditaia/restauraciondefotos/img/`.
- **Tu Canción:** la sección "Escuchá cómo suenan" de `index.html` e `index-base.html` tiene dos reproductores reales. Subí la carpeta `web/tucancion/audio/` completa (`muestra-cuadra-mia.mp3` y `muestra-radiografia.mp3`) a `/var/www/html/public/tutienditaia/tucancion/audio/`.
- No agregues otras canciones de muestra: solo van canciones originales.

## 2. Backend actualizado
1. Copiá `RegalosIA/tienda/app/` completo a `/srv/tutienditaia/app/app/`. Hay cambios posteriores a tu despliegue: link corto de revisión, `notification_url` y `auto_return` solo con https.
2. Corré los tests como usuario `tienda`: `sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests` (tienen que pasar 14).
3. `sudo systemctl restart tutienditaia` (restart, no reload).

## 3. Nginx: link corto de revisión (bloqueante)
En el `server` HTTPS de `/etc/nginx/sites-available/moodle`, agregá este bloque **antes** de `location ^~ /tutienditaia/`. Está también en `tienda/deploy/nginx-tutienditaia.conf`:
```
location ^~ /tutienditaia/revisar/ {
    proxy_pass http://127.0.0.1:8091/revisar/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```
Después: `sudo nginx -t && sudo systemctl reload nginx`.

## 4. Verificación (pegá las salidas al final de `tienda/docs/ENTREGA-ANTIGRAVITY.md`)
```bash
curl -s "https://campuscfp401avellaneda.com.ar/tutienditaia/revisar/RF-9999?t=x"     # {"detail":"Link inválido"}
curl -s -o /dev/null -w "%{http_code}\n" https://campuscfp401avellaneda.com.ar/tutienditaia/movil.css   # 200
curl -s -o /dev/null -w "%{http_code}\n" https://campuscfp401avellaneda.com.ar/tutienditaia/movil.js    # 200
curl -s -o /dev/null -w "%{http_code}\n" https://campuscfp401avellaneda.com.ar/tutienditaia/restauraciondefotos/img/muestra-despues.jpg   # 200
curl -s -o /dev/null -w "%{http_code}\n" https://campuscfp401avellaneda.com.ar/tutienditaia/tucancion/audio/muestra-cuadra-mia.mp3        # 200
curl -s https://campuscfp401avellaneda.com.ar/tutienditaia/api/salud                  # {"ok":true,"modo":"produccion"}
```
**No hagas pedidos de prueba:** la compra de prueba la hace Nicolás.
