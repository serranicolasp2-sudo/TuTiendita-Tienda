# Claves de la tienda: cómo sacarlas

Lo que necesita la tienda para cobrar, mandar mails y guardar los pedidos en Drive. Son 3 trámites, unos 30 minutos en total. Usá **una sola cuenta de Google para el negocio** (un Gmail nuevo, por ejemplo `tucancion.regalos@gmail.com`). No uses el Gmail de la escuela.

Todo lo que obtengas va en **un archivo en el Escritorio: `claves-tienda.txt`**, con este formato (copialo tal cual y completá):

```
MP_ACCESS_TOKEN=
MP_PUBLIC_KEY=
MP_WEBHOOK_SECRET=
MP_ACCESS_TOKEN_PRUEBA=
MP_PUBLIC_KEY_PRUEBA=
SMTP_USER=
SMTP_APP_PASSWORD=
WHATSAPP_NEGOCIO=549
NTFY_TOPIC=regalos-4afb1e868cd6
```

Además, en el Escritorio van a quedar dos archivos de Google: `client_secret_tienda.json` y `drive_token.json`.

**Nunca pegues una clave en el chat.** Si una clave se filtra, se regenera desde el mismo lugar donde la sacaste.

---

## 1. Mercado Pago: Access Token y webhook (15 min)

Hacelo con la cuenta de Mercado Pago **que va a recibir la plata**.

1. Entrá a **https://www.mercadopago.com.ar/developers/panel/app** con esa cuenta.
2. **Crear aplicación**:
   - Nombre: `Tienda Regalos`.
   - Tipo de solución: **Pagos online**.
   - ¿Usás una plataforma de e-commerce?: **No**.
   - Producto a integrar: **Checkout Pro**.
   - Aceptá y creá.
3. En el menú de la aplicación, entrá a **Credenciales de prueba**. Copiá la **Public Key** y el **Access Token** (empiezan con `TEST-` o `APP_USR-`) en `MP_PUBLIC_KEY_PRUEBA` y `MP_ACCESS_TOKEN_PRUEBA`. Con estas se hacen los primeros ensayos sin plata real.
4. Entrá a **Credenciales de producción** → **Activar credenciales**. Te pide:
   - Industria: *Arte / Entretenimiento* (o la más parecida).
   - Sitio web: `https://campuscfp401avellaneda.com.ar/tutienditaia` (después se cambia por el dominio propio).
   - Aceptá los términos. Copiá la **Public Key** en `MP_PUBLIC_KEY` y el **Access Token** (`APP_USR-…`) en `MP_ACCESS_TOKEN`.
5. En el menú, entrá a **Webhooks** → **Configurar notificaciones** (modo **productivo**):
   - URL: `https://campuscfp401avellaneda.com.ar/tutienditaia/api/mp/webhook`
   - Eventos: marcá solo **Pagos**.
   - Guardá. Aparece una **clave secreta** (con un botón de mostrar): copiala en `MP_WEBHOOK_SECRET`. Sirve para que la tienda verifique que el aviso viene de verdad de Mercado Pago.
   - Si te pide probar la URL y falla, no importa: todavía no está subido el servidor.

Importante: Mercado Pago no deja que una cuenta se pague a sí misma. Tu compra de prueba tiene que salir de **otra** cuenta de Mercado Pago, como pensabas.

## 2. Gmail del negocio: contraseña de aplicación para mandar mails (5 min)

1. Si todavía no existe, creá el Gmail del negocio.
2. Entrá a **https://myaccount.google.com/signinoptions/two-step-verification** con esa cuenta y activá la **verificación en dos pasos**. Es obligatoria para el paso siguiente.
3. Entrá a **https://myaccount.google.com/apppasswords**:
   - Nombre de la app: `Tienda`.
   - **Crear**. Aparece un código de 16 letras (en 4 grupos).
4. Copialo en `SMTP_APP_PASSWORD` y el Gmail en `SMTP_USER`.

Límite: Gmail deja mandar unos 500 mails por día, que sobra.

## 3. Google Drive: permiso para guardar los pedidos (10 min)

Con el **mismo Gmail del negocio**:

1. Entrá a **https://console.cloud.google.com/** y aceptá los términos si te los pide.
2. Arriba, en el selector de proyectos: **Proyecto nuevo** → nombre `tienda-regalos` → Crear. Fijate que quede seleccionado.
3. Entrá a **https://console.cloud.google.com/apis/library/drive.googleapis.com** y tocá **Habilitar**.
4. Entrá a **https://console.cloud.google.com/auth/overview** → **Comenzar**:
   - Nombre de la app: `Tienda Regalos`.
   - Correo de asistencia: el Gmail del negocio.
   - Público: **Externo**.
   - Información de contacto: el mismo Gmail.
   - Aceptá y **Crear**.
5. En el menú de la izquierda, entrá a **Público** → **Publicar app** → Confirmar, para que quede **En producción**. Si queda "en prueba", el permiso vence a los 7 días y la tienda deja de guardar en Drive.
6. En el menú, entrá a **Clientes** → **Crear cliente**:
   - Tipo de aplicación: **App de escritorio**.
   - Nombre: `tienda-pc`.
   - **Crear** → **Descargar JSON**.
   - Guardalo en el Escritorio como **`client_secret_tienda.json`**.
7. En tu PC, corré:
   ```
   python "C:\Users\Nicolás\Desktop\Proyectos\RegalosIA\tienda\herramientas\autorizar_drive.py"
   ```
   Se abre el navegador. Entrá con el Gmail del negocio y aceptá el permiso. Si aparece "Google no verificó esta app", tocá **Avanzado** → **Ir a Tienda Regalos**: la app es tuya.
8. Tiene que decir "Listo" y crear **`drive_token.json`** en el Escritorio. En el Drive del negocio aparece la carpeta **Pedidos Tienda**.

El permiso que se pide (`drive.file`) solo deja a la tienda ver y tocar las carpetas que ella misma crea. El resto del Drive le queda invisible.

## 4. Avisos al celular (2 min, sin cuenta)

1. Instalá la app **ntfy** (Play Store o App Store).
2. **+** → Suscribirse a un tema → `regalos-4afb1e868cd6` → Suscribirse.

Ahí te va a llegar cada pedido pagado, con un botón para abrir el WhatsApp del cliente con el mensaje ya escrito. El nombre del tema funciona como contraseña: no lo publiques.

## 5. Tu número de WhatsApp del negocio

Ponelo en `WHATSAPP_NEGOCIO` con el formato internacional sin `+` ni espacios: `549` + código de área sin 0 + número sin 15. Por ejemplo, `5491123456789`. Va en los botones de las webs y en los avisos.

## 6. Avisos por WhatsApp (opcional, 3 min, gratis)

El vigilante de proveedores (y más adelante otros avisos) puede escribirte por WhatsApp además de ntfy. Usa **CallMeBot**, un servicio gratuito que solo manda mensajes a tu propio número:

1. Entrá a https://www.callmebot.com/blog/free-api-whatsapp-messages/ y agendá el número del bot que figura **ahí** (cambia cada tanto; no uses uno de otra página).
2. Mandale por WhatsApp, tal cual: `I allow callmebot to send me messages`
3. En un par de minutos te responde con tu **apikey**.
4. Agregá en `claves-tienda.txt` (en el Escritorio, solo en la PC; no va al servidor):
   - `WHATSAPP_AVISOS=+549XXXXXXXXXX` (tu número, con `+549`)
   - `CALLMEBOT_APIKEY=` la clave que te mandó

Sin estas dos líneas los avisos siguen llegando solo por ntfy.

## 7. API de Mercado Libre (hecho el 13/10 con la cuenta SEPE947626)

> **Actualización 13/10:** el vigilante ya no usa la API (ML no deja leer publicaciones de otros vendedores); lee tus links meli.la (`ml_social.py`). La autorización queda para publicar en ML más adelante.

El vigilante revisa cada 30 minutos precio, vendedor y envío de los cuadros de proveedores (`tienda/herramientas/proveedores.json`) con la API oficial de ML, sin abrir navegadores, y ajusta solo el precio de venta.

**Antes:** tu cuenta de ML tiene que tener los datos del titular validados (en Argentina, ML no deja crear apps sin eso).

### Paso 1. Crear la aplicación
1. Entrá a https://developers.mercadolibre.com.ar/devcenter con tu cuenta de ML → **Crear nueva aplicación**.
2. Completá:
   - **Nombre**: `tutienditaia vigilante` (tiene que ser único; si ya existe, agregale algo).
   - **Nombre corto** (si lo pide): `tutienditaia`.
   - **Descripción**: `Consulta precios y envíos de proveedores para mi tienda`.
   - **Logo**: podés usar `marca/tutienditaia/export/tti-isologo-512.png`.
   - **URIs de redirect**: `https://campuscfp401avellaneda.com.ar/tutienditaia/api/ml/callback` (exacta, sin espacios ni barra al final).
   - **PKCE**: activado (es más seguro; el script ya lo usa).
   - **Permisos / scopes**: **Lectura** y **Acceso offline** (offline_access: sin esto el permiso vence a las 6 horas). Si te pide elegir por área, marcá solo lectura en "Usuarios" y en "Publicación y sincronización". **No** hace falta escritura.
   - **Tópicos / notificaciones**: ninguno. Si la URL de notificaciones es obligatoria, poné `https://campuscfp401avellaneda.com.ar/tutienditaia/api/ml/notificaciones`.
   - **Device grant**: no.
3. Guardá. En la ficha de la app vas a ver **App ID** (número) y **Secret Key** (clave secreta).

### Paso 2. Cargar las claves en la PC
Agregá al final de `claves-tienda.txt` (Escritorio; no va al servidor):
```
ML_APP_ID=el número del App ID
ML_CLIENT_SECRET=la Secret Key
ML_CP=tu código postal (para ver si "llega gratis mañana" ahí; por ejemplo 1872)
```

### Paso 3. Autorizar (una sola vez)
En una ventana de PowerShell:
```
python "C:\Users\Nicolás\Desktop\Proyectos\RegalosIA\tienda\herramientas\ml_api.py" autorizar
```
Se abre ML en tu navegador de siempre: iniciá sesión si te lo pide y tocá **Permitir**. La página siguiente te muestra un código con un botón **Copiar**: pegalo en la ventana de PowerShell y Enter. (Si la página da error porque todavía no está subida la tarea 8, copiá **la dirección completa** de esa página, que trae `?code=…`, y pegala.) El código dura unos minutos y sirve una sola vez.

Queda guardado en `Escritorio\ml_token.json` y se renueva solo. No lo compartas.

### Paso 4. Comprobar
```
python "C:\Users\Nicolás\Desktop\Proyectos\RegalosIA\tienda\herramientas\ml_api.py" probar
```
Tiene que mostrar las 4 publicaciones con ✓, su título, vendedor, precio y envío. Los enmarcados se buscan por título la primera vez: si alguno no es la publicación que elegiste, avisá (o poné su número MLA… en `item_id` de `proveedores.json`).

Desde ese momento el bot revisa solo cada 30 minutos. Si ML deja de renovar el permiso (por ejemplo, si cambiás la clave de la cuenta o revocás la app), te llega un aviso y repetís el paso 3.

---

Cuando el archivo esté completo, avisá. Las claves van del `.txt` al archivo `.env` del servidor (que no se publica). Después de eso conviene **borrar el `.txt` del Escritorio**.
