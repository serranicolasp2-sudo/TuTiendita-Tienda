# Tarea 4 para Antigravity: reemplazar el .env del servidor

**Diagnóstico de Claude:** después de la tarea 3, el pago sigue fallando con `Illegal header value b'Bearer '`: el `MP_ACCESS_TOKEN` del servidor está **vacío**. `claves-tienda.txt` tiene notas sueltas debajo de las claves, y el `.env` quedó mal armado. Claude generó uno limpio: `C:\Users\Nicolás\Desktop\env-servidor.txt`, solo con `KEY=valor`, finales de línea de Linux y la configuración del servidor ya incluida.

**No abras ni copies `claves-tienda.txt`.** Usá solamente `env-servidor.txt`.

```bash
# 1. Reemplazar el .env por el archivo limpio (subí Desktop\env-servidor.txt al servidor primero)
sudo cp env-servidor.txt /srv/tutienditaia/.env
sudo chown tienda:tienda /srv/tutienditaia/.env && sudo chmod 600 /srv/tutienditaia/.env
rm env-servidor.txt                                   # no dejar copias sueltas

# 2. Código nuevo (agrega /admin/diagnostico): copiá RegalosIA/tienda/app/ y tests/ a /srv/tutienditaia/app/
sudo chown -R tienda:tienda /srv/tutienditaia/app
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests   # 17 passed

# 3. Reiniciar
sudo systemctl restart tutienditaia && sudo systemctl is-active tutienditaia
```

No pegues en ningún lado el contenido del `.env`. Al terminar, anotá en `tienda/docs/ENTREGA-ANTIGRAVITY.md` solo "Tarea 4 hecha", la salida de pytest y la de `is-active`. Claude verifica con `/admin/diagnostico`, que muestra si cada clave está cargada sin mostrar su valor. No hagas pedidos de prueba.
