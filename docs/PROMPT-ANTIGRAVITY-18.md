# Tarea 18 para Antigravity: saber qué anuncio trajo cada pedido (UTM) y píxel de Meta

> **Estado (14/10, 18:55):** Antigravity la ejecutó y la subió a producción a las 15:50 **sin que el usuario se la pasara**. Claude la revisó (código, 40 + 32 pruebas, formularios en Android y iPhone, UTM y píxel en vivo): está bien hecha y no afecta el pago. **El usuario la aprobó a las 18:59 (D-56).** Desde ahora, regla 10 de `redes/AGENTS.md`: una propuesta no se ejecuta sin aprobación.

**PROPUESTA de Claude (14/10). No la empieces hasta terminar la 17 y que el usuario la apruebe.** Si hay que elegir, primero la parte A (sirve aunque no haya píxel).

Leé antes: `redes/AGENTS.md` (reglas comunes de redes), `redes/anuncios/ANUNCIOS.md`, `tienda/docs/CONTRATO-API.md` y lo que se corrigió en las fases anteriores de `centralita/ENTREGA.md`. Lo de siempre: no toques `.env`, las llaves ni la contraseña de root; **nada de pedidos de prueba con plata ni mails a clientes reales**; solo datos reales ("sin dato" si falta); lo que anotás como verificado lo miraste de verdad.

Por qué: los anuncios de Meta llevan a las webs con `?utm_source=meta&utm_medium=paid&utm_campaign=ddm2026&utm_content=P###` (P### es la pieza de `redes/`). Hoy ese dato se pierde al entrar al formulario, así que no hay forma de saber qué anuncio vendió.

## A. UTM en el pedido (webs + servidor + centralita)

1. **Webs** (`tienda/web/tienda.js`, las dos `index.html` e `index-base.html` si hace falta): al cargar la página, si la URL trae `utm_source`, `utm_medium`, `utm_campaign` o `utm_content`, se guardan en `sessionStorage` (la última visita con UTM gana) y viajan con el pedido en un campo `origen` = `{source, medium, campaign, content}`. Sin UTM, `origen` no se manda. Envolvé el acceso a `sessionStorage` en try/catch (navegación privada).
2. **Servidor** (`POST /pedidos` en `tienda/app/main.py`): `origen` es opcional; cada valor de hasta 60 caracteres con `[A-Za-z0-9_.-]`; lo que no cumple se descarta sin rechazar el pedido. Se guarda con el pedido y aparece en el `historial.txt` de la carpeta del pedido. Prueba nueva en `tienda/tests/`.
3. **Centralita:** columna "Origen" en la lista de pedidos (por ejemplo, "meta · P004") y un resumen por `utm_content`: pedidos pagados y monto cobrado, con datos reales de los pedidos.

## B. Píxel de Meta (solo si el usuario crea el píxel y te pasa su ID)

- El ID del píxel no es secreto, pero va en la configuración (no escrito a mano en cada HTML). Sin ID configurado, no se carga nada.
- Eventos: `PageView` en las páginas; `ViewContent` en cada web; `InitiateCheckout` al ir a pagar; `Purchase` en `gracias.html` **solo si el servidor confirma que el pago está aprobado**, con `value` (lo cobrado) y `currency: "ARS"`.
- **Sin datos personales**: nada de mail, teléfono ni nombre en los eventos (sin "coincidencia avanzada").
- En "Condiciones y garantías", Privacidad, una línea: "Usamos el píxel de Meta para saber qué anuncios funcionan. No le mandamos tus datos personales."
- En el celular, los pasos del formulario tienen que seguir andando: corré `produccion/pruebas/probar_pasos_movil.py` y anotá la salida.

## Al terminar

- Sección "Tarea 18" en `tienda/docs/ENTREGA-ANTIGRAVITY.md`: qué hiciste, pruebas, qué verificaste y dudas.
- Una entrada en `redes/BITACORA.md` (firma `Antigravity`, formato del registro) para que las IA de redes sepan que ya se puede medir.
