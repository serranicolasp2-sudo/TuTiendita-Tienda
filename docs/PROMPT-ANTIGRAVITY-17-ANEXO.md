# Tarea 17, anexo: precios terminados en 999 (D-53)

**Urgente, para hacer antes de cerrar la 17** (toca archivos que ya tenés abiertos). Decisión del usuario del 14/10: todos los precios pasan a **1 peso menos que el redondo** ($26.999, $4.999, $59.999…). Las piezas de redes y los anuncios del Día de la Madre ya salen con esos precios, y la campaña cierra el viernes 16/10.

Lo de siempre: no toques `.env`, las llaves ni la contraseña de root; nada de pedidos de prueba con plata ni mails a clientes reales; lo que anotás como verificado lo miraste de verdad.

## 1. Los 6 productos de precio fijo

**Los cargás vos** (el usuario lo decidió así el 14/10) y **es lo primero**: hasta que el servidor cobre estos precios no se puede publicar ninguna pieza de redes ni cargar los anuncios. Usá `POST /admin/precios`, la pantalla de Precios de la centralita o `python tienda/herramientas/precios_999.py --aplicar` (lee la clave de `claves-tienda.txt` sin mostrarla; sin `--aplicar` solo muestra el antes y el después). Después confirmá con `GET /catalogo`. Si el resto del anexo te lleva más tiempo, avisá en `redes/BITACORA.md` apenas estén cargados estos 6, así se empieza a publicar:

| Producto | Antes | Ahora |
|---|---|---|
| `rf-foto-1` | 5.000 | **4.999** |
| `rf-pack-5` | 15.000 | **14.999** |
| `rf-pack-10` | 25.000 | **24.999** |
| `rf-pack-20` | 39.900 | **39.999** |
| `tc-cancion` | 27.000 | **26.999** |
| `tc-combo` | 59.900 | **59.999** |

## 2. Cuadros: el vigilante redondea a $…999

Hoy `vigilante.precio_de_venta` redondea hacia arriba a $…900, y en modo automático vuelve a ese precio en cada vuelta (cada 30 min), así que cargar $34.999 a mano no alcanza. Cambiá el redondeo a **$…999 hacia arriba** (el primer número terminado en 999 que sea mayor o igual al bruto):

```python
return math.ceil((bruto + 1) / 1000) * 1000 - 1
```

Con eso, la ganancia neta nunca queda por debajo de la regla. Actualizá el docstring, las pruebas que esperan …900 y las cifras de ejemplo de los comentarios. Después de subirlo, corré `POST /admin/vigilante` y verificá en `GET /catalogo` que los 4 cuadros quedaron en …999. Los que estén en modo **fijo** no cambian: avisale al usuario cuáles son.

## 3. Valores de arranque en el código y en las webs

El servidor manda (D-51), pero los números escritos tienen que coincidir, para que no se vea un precio viejo mientras carga la página ni vuelva uno viejo si se pierde `precios.json`:

- `tienda/app/catalogo.py`: los precios de `PRODUCTOS` con los valores de la tabla (y los cuadros en el …999 que corresponda), más el comentario del 30x40.
- `web/tucancion/index.html` e `index-base.html`, `web/restauraciondefotos/index.html` e `index-base.html`, `web/movil.js`: el número inicial de cada `data-precio`.
- **`web/index.html` (el portal):** hoy tiene los precios escritos a mano y **no se actualizan solos** ("Desde $27.000 · Combo con video $59.900", "Desde $5.000"). Ponele `data-precio` y hacé que los pinte con el precio del servidor, como las otras webs. Los anuncios que muestran las dos marcas van a llevar al portal.
- `tienda/tests/` y `centralita/tests/`: lo que dependa de esos números.

## Al terminar

- En `tienda/docs/ENTREGA-ANTIGRAVITY.md`, dentro de la entrega de la 17, una sección "Anexo: precios terminados en 999" (qué cambiaste, pruebas y lo que muestra `GET /catalogo` después).
- Una entrada en `redes/BITACORA.md` (firma `Antigravity`) que diga si los 10 precios ya están en …999 en el servidor y si el portal ya los pinta en vivo: con eso las piezas de redes pasan la validación.
