# Contrato de la API de la tienda (para Antigravity)

El backend ya está hecho y probado (`tienda/app`, 14 pruebas y una prueba real contra Mercado Pago, Drive y Gmail). **Antigravity arma las webs y las conecta con esta API; no cambia el backend.** Si hace falta algo distinto, se le pide a Claude.

## Rutas en el servidor

| Qué | URL |
|---|---|
| Web Tu Canción | `https://campuscfp401avellaneda.com.ar/tutienditaia/tucancion/` |
| Web Restauración de fotos | `https://campuscfp401avellaneda.com.ar/tutienditaia/restauraciondefotos/` |
| Script del cliente (uno para las dos webs) | `https://campuscfp401avellaneda.com.ar/tutienditaia/tienda.js` (copiar `tienda/web/tienda.js` sin cambios) |
| API | `https://campuscfp401avellaneda.com.ar/tutienditaia/api/` |

Cada web necesita, además de su `index.html`, una página **`gracias.html`**: Mercado Pago vuelve ahí con `?pedido=TC-0001` (y `&pago=fallido` si no se pagó).

## Cómo se conecta un formulario (sin escribir JavaScript)

```html
<script src="/tutienditaia/tienda.js" defer></script>

<form data-tienda-form enctype="multipart/form-data">
  <input type="hidden" name="producto" value="rf-pack-5">
  … campos …
  <input type="text" name="sitio_web" tabindex="-1" autocomplete="off" hidden>   <!-- trampa para bots: siempre vacío -->
  <label><input type="checkbox" name="acepto" value="si" required> Acepto las condiciones y el uso de mis fotos para hacer el pedido</label>
  <p data-tienda-error hidden></p>
  <progress data-tienda-progreso hidden></progress>
  <button type="submit">Pagar con Mercado Pago</button>
</form>
```

`tienda.js` intercepta el envío, sube los archivos mostrando el progreso y redirige a Mercado Pago. Si hay un error, lo escribe en `[data-tienda-error]` y marca el campo con `aria-invalid="true"` (dale estilo a ese estado).

En `gracias.html` alcanza con `<div data-tienda-gracias></div>`: muestra el estado del pedido y se actualiza solo hasta que se confirma el pago.

Para elegir el producto, el formulario puede tener un `<select name="producto">` o radios con `name="producto"`, o un formulario por producto con el campo oculto. **El precio nunca se manda:** lo decide el servidor. Para mostrar precios, usá los del catálogo (`GET /catalogo`) o escribilos fijos con los mismos valores.

## Campos

### Comunes (todos los productos)
| Nombre | Obligatorio | Notas |
|---|---|---|
| `producto` | sí | id del catálogo (tabla de abajo) |
| `nombre` | sí | hasta 120 caracteres |
| `email` | sí | |
| `whatsapp` | sí | como lo escriba la persona (`11 15 2345 6789`, `+54 9 11…`); el servidor lo normaliza |
| `comentarios` | no | observaciones adicionales, hasta 3000 caracteres |
| `acepto` | sí | checkbox con `value="si"` |
| `sitio_web` | — | oculto, **siempre vacío** |

### Restauración de fotos
| Nombre | Obligatorio | Notas |
|---|---|---|
| `fotos` | sí | `<input type="file" name="fotos" accept="image/*,.heic,.heif" multiple>`; JPG, PNG, WEBP, HEIC o TIFF; **15 MB por foto como máximo**; cantidad según el producto |
| `color` | no | `Color` / `Mantener colores de época` / `Blanco y negro` |

### Cuadros (además de los de fotos; 1 foto)
`envio_destinatario` (no; por defecto, el nombre), `envio_calle`, `envio_numero`, `envio_piso` (no), `envio_localidad`, `envio_provincia`, `envio_cp`, `envio_dni` (lo pide la mensajería). Todos obligatorios salvo los marcados.
Cuadro enmarcado (`rf-cuadro-enmarcado-20x30`): además `marco` = `Madera` / `Negro` (obligatorio; el catálogo lo publica en `marcos`).

Texto que tiene que estar cerca de los cuadros: *"¿Otra medida? Comprá la restauración de 1 foto y coordinamos el formato y el envío por WhatsApp."* (con el botón de WhatsApp).

### Canción (`tc-cancion` y `tc-combo`)
| Nombre | Obligatorio | Notas |
|---|---|---|
| `para_quien` | sí | nombre de la persona agasajada (y cómo le dicen) |
| `vinculo` | no | mamá, pareja, amiga… |
| `ocasion` | no | cumpleaños, aniversario, Día de la Madre… |
| `estilos` | sí, al menos 1 | checkboxes `name="estilos"` con valores **exactos** de `catalogo.estilos`: Balada, Pop, Cumbia, Cuarteto, Folklore, Rock nacional, Bolero, Tango, Reggaetón suave, Infantil, Acústico, Otro |
| `estilo_otro` | no | texto, si eligió "Otro" |
| `voz` | sí | radio con valor exacto: `Femenina` / `Masculina` / `Me da igual` |
| `inspiracion` | no | link de YouTube (`https://…`) de una canción que le guste como referencia |
| `historia` | sí, 40 caracteres o más | de qué querés que hable, datos de la persona, anécdotas, características, momentos importantes (textarea grande, con ejemplos en el placeholder) |
| `evitar` | no | algo que NO tiene que aparecer |
| `duracion` | sí | valor exacto: `Corta (unos 2 minutos)` / `Normal (unos 3 minutos)` / `Larga (unos 4 minutos)` |
| `fotos` | solo en `tc-combo` | de 1 a 20 fotos para el video |

## Productos (los precios los decide el servidor)

| id | Web | Producto | Precio | Fotos |
|---|---|---|---|---|
| `rf-foto-1` | fotos | Restauración de 1 foto | $5.000 | 1 |
| `rf-pack-5` | fotos | Pack de 5 fotos | $15.000 | 1–5 |
| `rf-pack-10` | fotos | Pack de 10 fotos | $25.000 | 1–10 |
| `rf-pack-20` | fotos | Pack de 20 fotos | $39.900 | 1–20 |
| `rf-cuadro-ecocuero-20x30` | fotos | Cuadro ecocuero en bastidor 20x30 | $34.900 | 1 + dirección |
| `rf-cuadro-ecocuero-40x30` | fotos | Cuadro ecocuero en bastidor 40x30 | $44.900 | 1 + dirección |
| `rf-cuadro-enmarcado-20x30` | fotos | Cuadro enmarcado 20x30 | $23.000 | 1 + dirección |
| `tc-cancion` | canción | Canción con tu historia | $27.000 | — |
| `tc-combo` | las dos | Canción + video con fotos | $59.900 | 1–20 |

## Endpoints (referencia; `tienda.js` ya los usa)

- `GET /catalogo?marca=tc|rf` → `{productos:[{id, nombre, precio, detalle, fotos_min, fotos_max, cancion, envio}], estilos, voces, duraciones, whatsapp, transferencia:{alias, cbu}}`
- `POST /pedidos` (multipart) → `201 {pedido, precio, producto, init_point}` · `422 {error, campo}` · `429` · `502`
- `GET /pedidos/{id}/estado` → `{pedido, estado, producto, marca, precio, transferencia_avisada}`; estados: `pendiente_pago`, `pagado`, `entregado`, `cancelado`
- `GET /pedidos/{id}/pagar` → `{pedido, init_point}`: el link de Mercado Pago del mismo pedido para reintentar (`409` si ya no espera el pago)
- `POST /pedidos/{id}/transferencia` → `{ok, pedido, monto, alias, cbu}`: el cliente avisa que paga por transferencia; al dueño le llega un aviso al celular (una vez por pedido). El pedido sigue `pendiente_pago` hasta que el dueño lo aprueba
- `POST /mp/webhook`: solo Mercado Pago (firma verificada)
- `/admin/...`: solo el dueño, con token. Nuevos (17/10): `POST /admin/pedidos/{id}/transferencia` (aprobar un pago por transferencia: pasa a pagado y arranca como cualquier pago) y `GET /admin/interesados` (quienes empezaron un pedido y no lo pagaron, uno por mail)

**Vuelta de Mercado Pago (17/10):** `gracias.html?pedido=…` en el dominio de cada marca (`URL_WEB_TC` / `URL_WEB_RF`). Si el pago no se completó (`pago=fallido`, o `collection_status`/`status` `null` o `rejected`), `tienda.js` muestra "¿No pudiste realizar la compra?" con el botón para reintentar y los datos de transferencia. Sin datos de Mercado Pago en la dirección, aparece a los 15 s si el pedido sigue sin pagar.

**Formulario sin pago con link de un solo uso (17/10):** `https://<web de la marca>/?canje=TOKEN`. `tienda.js` pide `GET /canje/{token}` → `{estado: valido|usado|vencido, tipo: regalo|mercadolibre, producto, nombre, marca}`, toca la tarjeta del producto, esconde las demás, saca precio y Mercado Pago y manda `canje` con el formulario. `POST /pedidos` con `canje` válido: el producto lo fija el link, el pedido queda `pagado` (precio 0, `pago_medio` regalo o mercadolibre) y responde `{pedido, pagado: true}`; `422 campo=canje` si el link se usó o venció. Links: `POST /admin/canjes` (Mercado Libre: `{tipo: mercadolibre, producto, orden}`, uno por orden, 30 días; los cuadros no) o el mail de regalo (14 días). En la PC: `python pedidos.py link-ml <orden>`.

**Foto de regalo (17/10):** a los 30 minutos sin pago el servidor manda un mail con reintento, transferencia y un link de un solo uso para la restauración de 1 foto. Uno por mail y por WhatsApp; no se manda si hay un pago en efectivo pendiente (se reintenta en cada vuelta).

**Avisos al dueño (ntfy):** pedido sin pagar a los `MINUTOS_AVISO_SIN_PAGO` (30) con el WhatsApp del cliente listo; transferencia avisada; error al crear el pago. Los pedidos sin pagar vencen a las 72 h, o a los 7 días si el cliente avisó transferencia.

## Qué pasa después del pago (automático, no lo hace la web)
Carpeta en Drive "Pedidos Tienda/TC-0001 · Nombre" con las fotos y `pedido.txt` → mail al cliente con los próximos pasos → mail y notificación al dueño con botones para abrir Drive y el WhatsApp del cliente.

## Lo que Antigravity NO tiene que hacer
- Calcular ni mandar precios.
- Guardar fotos o datos en otro lado (ni localStorage, ni otra API).
- Poner claves en el HTML. La web no necesita ninguna: la Public Key de Mercado Pago no hace falta con Checkout Pro.
- Modificar `tienda.js`: si hace falta algo, se pide.
