# Tarea 21 · Mercado Libre: precio propio, fotos limpias y que no se vuelva a romper

De: Claude. 15/10/2026. **Urgente**: se publicó en ML con el precio de la web y cada venta dejaba menos que la web (los tres cuadros más grandes, menos que el costo del proveedor). Ya lo corregí a mano en ML (D-60); esta tarea es para que tu herramienta no lo vuelva a romper.

> Para el usuario: pasale a Antigravity **"Leé tienda/docs/PROMPT-ANTIGRAVITY-21.md y hacelo."**

## Antes de empezar

1. Leé `DECISIONES.md` D-59 y **D-60**, y `tienda/herramientas/precios_ml.py` (nuevo, mío).
2. Corré `python tienda/herramientas/precios_ml.py` (sin `--aplicar`): las 10 publicaciones tienen que decir `ok`.
3. **No publiques, no cierres ni cambies precios en ML mientras trabajás**, salvo lo que pide el punto 4, y no toques la web ni sus precios.

## Lo que tenés que hacer

1. **`publicar_ml.py` publica con el precio de ML, no con el de la web.** En `armar_payload`, el precio sale de `precios_ml` (el mismo cálculo: el menor terminado en 999 que deja lo mismo que la web, con el cargo real de `listing_prices`, el envío gratis obligatorio y el % real de MP). Si falta un dato, no publica ese producto y lo dice.
2. **Seguir los cambios del vigilante.** Cuando el vigilante cambia un precio de la web (o se aprueba uno a mano en la centralita), hay que correr `precios_ml.py --aplicar`. Proponé dónde (en el ciclo de la centralita o del bot de la PC, cada 30 minutos como el vigilante) y ponelo. Respetá el límite de ML: hoy dio `429 local_rate_limited` al cambiar 10 precios seguidos; esperá entre llamadas y reintentá.
3. **Centralita, pestaña Mercado Libre y Meta:** por publicación, mostrá lo que queda en ML (precio − cargo − envío a cargo) al lado de lo que queda en la web, y marcá en rojo si ML deja menos. Si hubiera estado, el problema se veía en la pantalla.
4. **Plantillas de `publicar_ml.py`** (no las publicaciones en vivo, que ya corregí):
   - Fotos: usar las de `tienda/ml-fotos/` (sin precio, dominio, @ ni WhatsApp; las genera `fotos_ml.py`). ML desenfocó seis veces fotos de la canción y el combo por "datos de contacto" y marcó la ficha técnica de la canción.
   - Descripciones: copiar las que quedaron en vivo (las leés con `GET /items/{id}/description`). En los cuadros desde $33.000 **no hay retiro**: el aviso dice "Envío gratis por Mercado Envíos"; solo el enmarcado 20x30 (que queda debajo de $33.000) mantiene el aviso de retiro. Nada de "WhatsApp" ni "chat privado": "la mensajería de Mercado Libre".
   - No volver a crear una publicación que ya existe: buscar por título **incluyendo las pausadas, en revisión y pendientes** (hoy hay 5 duplicadas frenadas por "categoría incorrecta").
5. **Tests**: una prueba de `precios_ml` con cargos y envío simulados (que el precio cubra lo de la web, que termine en 999, que sin dato no cambie nada).

## Lo que NO hacés

- Cambiar precios de la web o reglas del vigilante.
- Cerrar, pausar o borrar publicaciones (lo decide el usuario).
- Activar cuotas sin interés o publicidad de ML (suben el costo; lo decide el usuario).

## Al terminar

Entrada en `tienda/docs/ENTREGA-ANTIGRAVITY.md` (§ nueva) con lo hecho, pruebas y la salida de `precios_ml.py` (todas `ok`). "Para: Claude: revisar la tarea 21".
