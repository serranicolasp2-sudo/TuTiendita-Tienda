# Tu Tiendita IA · Tienda & Bot Backend

> **Sitio web oficial:** [tutiendita-ia.store](https://tutiendita-ia.store)  
> Sistema de comercio electrónico, gestión de pedidos y bot autónomo para personalización y regalos con Inteligencia Artificial.

---

## 🌟 Descripción del Proyecto

**Tu Tiendita IA - Tienda** es el núcleo transaccional y backend de la plataforma. Procesa compras de canciones personalizadas, restauraciones fotográficas y combos multimedia. Integra pasarelas de pago, bots de procesamiento desatendido, sincronización con MercadoLibre y alertas en tiempo real.

---

## 🚀 Características Principales

1. **API REST con FastAPI**:
   - Catálogo de productos, combos y opciones de enmarcado.
   - Creación y seguimiento de pedidos en tiempo real.
   - Subida segura de archivos fotográficos y especificaciones para canciones.

2. **Integración con Mercado Pago**:
   - Cobro por checkout pro y webhook automatizado.
   - Reconciliación de pagos pendientes e idempotencia estricta.

3. **Bot Autónomo de Pedidos (`herramientas/bot.py`)**:
   - Monitoreo continuo de nuevos pedidos pagados.
   - Orquestación de carpetas de producción local (`C:\Pedidos`).
   - Envío de prompts a modelos de IA para composición lírica y restauración.

4. **Vigilante de Proveedores y Precios**:
   - Monitoreo automático de costos de insumos (cuadros, bastidores, impresiones).
   - Ajuste dinámico de precios respetando el margen neto comercial.

5. **Notificaciones Multicanal**:
   - Notificaciones push inmediatas mediante ntfy.
   - Alertas por WhatsApp Business (CallMeBot).
   - Emails transaccionales con confirmación de pedido y entregas.

6. **Backup y Sincronización en Google Drive**:
   - Respaldo de archivos de clientes y entregas finales.

---

## 🛠️ Tecnologías Utilizadas

- **Lenguaje:** Python 3.11+
- **Framework Web:** FastAPI, Starlette, Uvicorn
- **Base de Datos:** SQLite3 (módulo nativo estándar, almacenamiento transaccional local sin sobrecarga de ORMs)
- **Integración de Pagos:** `httpx` para llamadas REST asíncronas directas a la API de Mercado Pago, verificación criptográfica de firmas HMAC-SHA256 en webhooks y control de idempotencia
- **Orquestación de IA:** Integración desatendida por CLI con Claude y Codex (`herramientas/claudecli.py`, `herramientas/codexcli.py`)
- **Testing:** Suite completa de pruebas con Pytest (46 tests automatizados pasando al 100%)

---

## ⚙️ Estructura del Proyecto

```text
tienda/
├── app/                  # Núcleo del servidor FastAPI
│   ├── main.py           # Endpoints de la API y rutas públicas/admin
│   ├── catalogo.py       # Definición de productos, combos y precios
│   ├── pagos.py          # Lógica de cobros y estados
│   ├── mp.py             # Integración directa con Mercado Pago
│   ├── flujo.py          # Máquina de estados de pedidos
│   ├── vigilante.py      # Tareas en segundo plano
│   └── avisos.py         # Notificaciones ntfy y WhatsApp
├── herramientas/         # Scripts y bots operativos
│   ├── bot.py            # Bot principal de procesamiento
│   ├── proveedores.py    # Vigilante de precios de proveedores
│   ├── restauracion.py   # Automatización de tareas de restauración
│   ├── letras.py         # Asistente de composición lírica
│   └── ml_api.py         # Publicador e integrador con MercadoLibre
├── ml-fotos/             # Plantillas y piezas gráficas para publicaciones
├── docs/                 # Guías de configuración y claves
└── deploy/               # Archivos de despliegue y systemd
```

---

## 📦 Puesta en Marcha

1. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configuración de claves:**
   Seguir la guía detallada en `docs/CLAVES.md`. Las claves se cargan mediante variables de entorno o archivo de configuración local externo.

3. **Ejecutar el servidor localmente:**
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

4. **Ejecutar el bot de procesamiento:**
   ```bash
   python herramientas/bot.py
   ```

---

## 🌐 Identidad de Marca

Este proyecto forma parte del ecosistema oficial de **Tu Tiendita IA**  
Sitio Web: [tutiendita-ia.store](https://tutiendita-ia.store)
