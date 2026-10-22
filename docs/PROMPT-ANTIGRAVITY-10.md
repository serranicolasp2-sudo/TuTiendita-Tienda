# Tarea 10 para Antigravity: revisión del mail del cliente (formulario y servidor) + "¿No la puedo hacer yo con una IA?" en las webs

Todo lo hizo y probó Claude. **No modifiques nada: solo subilo y verificá.** No toques `DATOS_DIR` ni el `.env`.

Por qué: un cliente escribió su mail terminado en "@gmail.col" y todos los avisos rebotaron.
- `tienda.js` (el script compartido de las dos webs) ahora revisa el formato y los errores de tipeo en los proveedores conocidos (gmail.col, gmial.com, hotmail.con…): muestra "¿Quisiste decir …@gmail.com?" con dos botones y no deja seguir hasta que el cliente elija.
- El servidor revisa lo mismo (`app/correo.py`) y además consulta el DNS: si el dominio no existe o no recibe correo, no toma el pedido. Para eso suma la librería `dnspython` (si faltara, el servidor sigue andando sin esa consulta).

## A. Backend
```bash
# Copiá RegalosIA/tienda/app/ (incluye el nuevo correo.py), RegalosIA/tienda/tests/ y RegalosIA/tienda/requirements.txt
# a /srv/tutienditaia/app/ (pisando lo anterior)
sudo chown -R tienda:tienda /srv/tutienditaia/app
cd /srv/tutienditaia/app && sudo -u tienda /srv/tutienditaia/venv/bin/pip install -r requirements.txt
sudo -u tienda /srv/tutienditaia/venv/bin/python -c "import dns.resolver; print('dnspython ok')"
sudo -u tienda env TIENDA_AUTOARRANQUE=0 /srv/tutienditaia/venv/bin/python -m pytest -q tests
#   Esperado con los precios de prueba de $500: "4 failed, 20 passed" (las 4 de siempre). Otra falla: frená y anotala.
sudo systemctl restart tutienditaia && sudo systemctl is-active tutienditaia
```

## B. Script y páginas de las webs
- `RegalosIA/tienda/web/tienda.js` → `/var/www/html/public/tutienditaia/tienda.js` (copia exacta, pisando la anterior).
- Las dos webs suman la sección "¿No la puedo hacer yo con una IA?" (por qué comprarnos a nosotros), una pregunta frecuente y, en fotos, una línea en el cruce a canciones. Copiá exacto, pisando lo anterior (no subas `img/` ni `audio/`, no cambiaron):
  - `RegalosIA/web/tucancion/index.html` e `index-base.html` → `/var/www/html/public/tutienditaia/tucancion/`
  - `RegalosIA/web/restauraciondefotos/index.html` e `index-base.html` → `/var/www/html/public/tutienditaia/restauraciondefotos/`

## C. Verificación
```bash
B=https://campuscfp401avellaneda.com.ar/tutienditaia
curl -s $B/tienda.js | grep -c "sugerirMail"                     # 2 o más
curl -s $B/tucancion/ | grep -c 'id="por-que"'                   # 1
curl -s $B/restauraciondefotos/ | grep -c 'id="por-que"'         # 1
# Un pedido con el mail mal escrito: el servidor lo rechaza ANTES de crear nada (no es un pedido de prueba)
curl -s -F producto=rf-foto-1 -F nombre=Prueba -F email=prueba@gmail.col -F whatsapp=1155069569 -F acepto=si $B/api/pedidos
#   Esperado: {"error":"¿Quisiste decir prueba@gmail.com? …","campo":"email"}
curl -s -F producto=rf-foto-1 -F nombre=Prueba -F email=prueba@gmail.col -F email_revisado=si -F whatsapp=1155069569 -F acepto=si $B/api/pedidos
#   Esperado: {"error":"Ese mail no puede recibir correos: «gmail.col» no existe. …","campo":"email"}
```
Anotá "Tarea 10 hecha" y las salidas al final de `tienda/docs/ENTREGA-ANTIGRAVITY.md`. No hagas pedidos de prueba completos.
