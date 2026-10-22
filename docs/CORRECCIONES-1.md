# Correcciones 1, tras la revisión de Claude (04/10/2026)

Revisión en vivo de la entrega de Antigravity. **Está bien:**
- API `/salud` en producción, catálogo con los 9 productos y `tienda.js` idéntico al original (mismo hash).
- Las 6 páginas responden 200.
- El webhook sin firma devuelve 401, `/admin` sin token devuelve 401 y no se ven `.env`, `tienda.db` ni `/docs`.
- Formularios: los campos coinciden 100% con el contrato.
- Los 8 productos de la web de fotos activan sus campos y no quedan campos obligatorios ocultos.
- En un celular de 375 px no hay desborde horizontal: el corte de `cancion_mobile.png` es un defecto de la captura.
- Una foto de 12 MB atraviesa Nginx hasta la API.

## C1 (bloqueante): falta el link corto de revisión en Nginx
`https://campuscfp401avellaneda.com.ar/tutienditaia/revisar/RF-9999?t=x` devuelve **404 de Nginx**. Es el link que recibe el cliente para aprobar la vista previa o pedir un cambio: sin esto, el cliente no puede aprobar.

Pegale esto a Antigravity:

---
En el servidor:
1. Volvé a copiar `RegalosIA/tienda/app/` completo a `/srv/tutienditaia/app/app/` (hubo cambios después de tu despliegue: link corto de revisión, `notification_url` y `auto_return` solo si son https). Corré los tests como usuario `tienda` (tienen que pasar 14) y después `sudo systemctl restart tutienditaia`.
2. En el `server` HTTPS de `/etc/nginx/sites-available/moodle`, agregá este bloque **antes** de `location ^~ /tutienditaia/` (está en `tienda/deploy/nginx-tutienditaia.conf`):
```
location ^~ /tutienditaia/revisar/ {
    proxy_pass http://127.0.0.1:8091/revisar/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```
3. `sudo nginx -t && sudo systemctl reload nginx`
4. Verificá: `curl -s "https://campuscfp401avellaneda.com.ar/tutienditaia/revisar/RF-9999?t=x"` tiene que devolver `{"detail":"Link inválido"}` (404 de la API, no la página de Nginx).
5. Anotá el resultado al final de `tienda/docs/ENTREGA-ANTIGRAVITY.md`.
---
