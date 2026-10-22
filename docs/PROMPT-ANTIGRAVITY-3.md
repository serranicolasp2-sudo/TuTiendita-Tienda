# Tarea 3 para Antigravity: arreglo del error 500 al pagar (urgente)

**Causa (diagnóstico de Claude):** `/srv/tutienditaia/.env` quedó con finales de línea de Windows (`\r\n`). systemd no saca el `\r`, así que el token de Mercado Pago queda como `APP_USR-…\r`. httpx rechaza ese encabezado (`LocalProtocolError: Illegal header value`) y la API devuelve 500 al crear el pago. El mismo `\r` rompe la clave secreta del webhook y la contraseña de Gmail.

Claude ya corrigió el código (`app/config.py` limpia los valores y `app/main.py` nunca devuelve un 500 mudo; 16 pruebas). **No modifiques nada**: ejecutá esto en el servidor:

```bash
# 1. Sacar los \r del .env (no cambia ningún valor)
sudo sed -i 's/\r$//' /srv/tutienditaia/.env
sudo grep -c $'\r' /srv/tutienditaia/.env          # tiene que dar 0
sudo chown tienda:tienda /srv/tutienditaia/.env && sudo chmod 600 /srv/tutienditaia/.env

# 2. Código nuevo: copiá RegalosIA/tienda/app/ y RegalosIA/tienda/tests/ a /srv/tutienditaia/app/ (pisando lo anterior)
sudo chown -R tienda:tienda /srv/tutienditaia/app
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests   # 16 passed

# 3. Reiniciar (restart, no reload)
sudo systemctl restart tutienditaia
sudo systemctl is-active tutienditaia              # active
curl -s https://campuscfp401avellaneda.com.ar/tutienditaia/api/salud
```

Pegá las salidas al final de `tienda/docs/ENTREGA-ANTIGRAVITY.md`. **No hagas pedidos de prueba:** Claude verifica en vivo y después paga Nicolás.

Si `drive_token.json` lo copiaste desde Windows, también puede tener `\r`, pero como es JSON no le afecta. No lo toques.
