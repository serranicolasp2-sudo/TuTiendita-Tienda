# Tarea para Antigravity: webs con venta automatizada y subida al servidor

Copiá y pegá esto en Antigravity:

---

Proyecto `C:\Users\Nicolás\Desktop\Proyectos\RegalosIA`. Antes de empezar, leé `DECISIONES.md` (D-12 a D-17), `tienda/docs/CONTRATO-API.md` y `tienda/deploy/INSTALAR.md`. **El backend ya está hecho y probado por Claude: no lo modifiques.** Si te hace falta algo de la API, anotalo en `tienda/docs/PEDIDOS-A-CLAUDE.md`.

## A. Webs (partí de lo que ya existe en `web/tucancion/` y `web/restauraciondefotos/`)
1. Mantené los dos sistemas de diseño tal cual (Tu Canción: `marca/tu-cancion/`; Restauración de fotos: `marca/restauracion-de-fotos/`) y la campaña del Día de la Madre (`index.html` con campaña, `index-base.html` sin campaña).
2. Sumá a cada web una **sección de compra** con formularios que respeten **exactamente** los nombres de campo del contrato, `data-tienda-form` y `<script src="/tutienditaia/tienda.js" defer>`:
   - **Restauración de fotos:** cards de producto con precio: 1 foto $5.000, 5 fotos $15.000, 10 fotos $25.000, 20 fotos $39.900, cuadro ecocuero bastidor 20x30 $34.900, cuadro ecocuero bastidor 40x30 $44.900, cuadro enmarcado 20x30 $23.000. Al elegir una, se abre su formulario: adjuntar fotos (con la cantidad máxima visible y vista previa en miniatura), color (mantener / color / blanco y negro), comentarios, datos de contacto y, si es cuadro, la dirección de envío. Agregá la línea: "¿Otra medida? Comprá la restauración de 1 foto y coordinamos el formato y el envío por WhatsApp".
   - **Tu Canción:** formulario de canción ($27.000) con para quién, vínculo, ocasión, estilos (checkboxes), voz, link de inspiración de YouTube, la historia (textarea grande, con un placeholder que guíe: de qué querés que hable, datos de la persona, anécdotas, características, momentos importantes), qué evitar y duración. El combo ($59.900) es el mismo formulario más las fotos (hasta 20). El combo aparece en las dos webs.
   - Botón: "Pagar con Mercado Pago". Debajo, en chico: "Pago seguro con Mercado Pago. Te llevamos a su página para pagar."
   - Checkbox `acepto` que enlace a una sección o página corta de **condiciones**:
     - entrega digital en 48 h hábiles desde el pago;
     - vista previa antes de la entrega;
     - canción con hasta 5 cambios; foto con 1 corrección;
     - las fotos se borran a los 30 días y nunca se publican sin permiso;
     - si la cara de la foto está destruida y no se puede restaurar, se devuelve el dinero;
     - las canciones se hacen con inteligencia artificial y las revisa una persona.
3. Creá `gracias.html` en cada web con `<div data-tienda-gracias></div>`, con el mismo diseño.
4. Creá `/tutienditaia/index.html`: una portada simple que lleve a las dos tiendas (es la URL que figura en Mercado Pago). Usá el isologo aprobado `marca/tutienditaia/export/tti-isologo-512.png` (toldo con "tutiendita IA", fondo birome) y como ícono de la pestaña `tti-favicon-32.png` y `tti-apple-touch-icon-180.png`.
5. Accesibilidad: labels reales, foco visible, estilo para `[aria-invalid="true"]`, errores legibles y que todo funcione en el celular. Los botones de WhatsApp ya tienen el número real.

## B. Rutas finales
- `https://campuscfp401avellaneda.com.ar/tutienditaia/` → portada
- `…/tutienditaia/tucancion/`
- `…/tutienditaia/restauraciondefotos/` 
- `…/tutienditaia/tienda.js` ← `tienda/web/tienda.js`, **sin modificar**
- `…/tutienditaia/api/` ← backend

Revisá los links internos (logos, imágenes, CSS) para que funcionen bajo esas rutas.

## C. Servidor
Seguí `tienda/deploy/INSTALAR.md` **al pie de la letra**: usuario `tienda`, `/srv/tutienditaia`, servicio `tutienditaia` y el bloque de Nginx con `^~` antes de las reglas de Moodle. **No toques nada de Moodle ni del campus** salvo para pegar ese bloque. Las claves salen de `C:\Users\Nicolás\Desktop\claves-tienda.txt` y `drive_token.json`: van solo al `.env` y a `secretos/` del servidor, nunca al repo ni a las webs. Para la primera prueba, `MP_MODO=produccion` (Nicolás va a pagar desde otra cuenta).

## D. Al terminar, dejá en `tienda/docs/ENTREGA-ANTIGRAVITY.md`
- Qué archivos cambiaste.
- Salida de `pytest` en el servidor (14 passed).
- `curl …/tutienditaia/api/salud` y `…/catalogo`.
- Capturas de los formularios en celular y en computadora.
- Cualquier cosa que no funcionó.

Claude revisa todo antes de la compra de prueba.
