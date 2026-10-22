"""Lo que pasa cuando un pedido se paga y cuando se entrega."""
import logging
import pathlib
import shutil
import urllib.parse
from datetime import datetime, timedelta, timezone

from . import avisos, catalogo
from .db import ahora

log = logging.getLogger("tienda")

MARCAS = {"tc": "Tu Canción", "rf": "Restauración de fotos"}
DIAS_RETENCION = 30   # lo que prometen las condiciones de las dos webs

ETIQUETAS = {
    "para_quien": "Para quién es", "vinculo": "Qué es para vos", "ocasion": "Ocasión",
    "estilos": "Estilos", "estilo_otro": "Otro estilo", "voz": "Voz", "inspiracion": "Inspiración (link)",
    "historia": "Historia para la letra", "evitar": "Qué no tiene que aparecer", "duracion": "Duración",
    "comentarios": "Comentarios", "color": "Color", "marco": "Color del marco", "envio": "Envío",
    "origen": "Origen",
}


def quedan_cambios(n: int) -> str:
    if n <= 0:
        return "Ya usaste los cambios incluidos."
    return f"Te queda {n} cambio." if n == 1 else f"Te quedan {n} cambios."


def resumen(p: dict) -> str:
    prod = catalogo.PRODUCTOS[p["producto"]]
    lineas = [f"Pedido {p['id']} · {MARCAS[p['marca']]}", f"Producto: {prod.nombre}", f"Precio: ${p['precio']:,}".replace(",", "."),
              f"Cliente: {p['nombre']}", f"Email: {p['email']}", f"WhatsApp: +{p['whatsapp']}", f"Creado: {p['creado']}"]
    if p.get("pagado"):
        if p.get("pago_medio") == "transferencia":
            lineas.append(f"Pagado: {p['pagado']} (transferencia, aprobada a mano con el comprobante)")
        elif p.get("pago_medio") == "regalo":
            lineas.append(f"Pedido de regalo: {p['pagado']} (foto de regalo; link de un solo uso)")
        elif p.get("pago_medio") == "mercadolibre":
            lineas.append(f"Compra de Mercado Libre: {p['pagado']} (cobrado en ML; link de un solo uso)")
        else:
            lineas.append(f"Pagado: {p['pagado']} (pago MP {p.get('mp_pago')})")
    for k, v in p["datos"].items():
        if v in (None, "", []):
            continue
        if isinstance(v, dict):
            v = ", ".join(f"{a}: {b}" for a, b in v.items() if b)
        elif isinstance(v, list):
            v = ", ".join(v)
        lineas.append(f"{ETIQUETAS.get(k, k)}: {v}")
    if p["archivos"]:
        lineas.append(f"Fotos adjuntas: {len(p['archivos'])}")
    return "\n".join(lineas)


def _que_sigue(p: dict) -> str:
    prod = catalogo.PRODUCTOS[p["producto"]]
    if prod.cancion:
        video = " El video con las fotos llega en hasta 72 horas." if prod.fotos_max else ""
        return ("En menos de 48 horas te mandamos por WhatsApp el primer minuto de la canción para que la escuches. "
                "Podés pedir hasta 5 cambios; cuando la aprobás, te llega completa en MP3." + video)
    if prod.envio:
        return ("En menos de 2 horas te mandamos la vista previa de la foto restaurada. Cuando la aprobás, "
                "encargamos el cuadro y te avisamos el seguimiento del envío.")
    return ("En menos de 2 horas te mandamos la vista previa con marca de agua. "
            "Cuando la aprobás, te llega en alta calidad por mail y WhatsApp.")


def al_pagar(cfg, base, drive, pid: str):
    """Pedido pagado: carpeta en Drive con fotos y datos, mail al cliente y aviso al dueño. Se puede repetir sin duplicar."""
    p = base.obtener(pid)
    try:
        if not p.get("drive_carpeta"):
            carpeta = drive.carpeta(f"{p['id']} · {p['nombre']}")
            base.actualizar(pid, drive_carpeta=carpeta["id"], drive_url=carpeta["webViewLink"])
            p = base.obtener(pid)
            if p["archivos"]:
                originales = drive.carpeta("originales", carpeta["id"])
                for ruta in p["archivos"]:
                    drive.subir(ruta, originales["id"])
            txt = pathlib.Path(cfg.datos_dir) / "subidas" / pid / "pedido.txt"
            txt.parent.mkdir(parents=True, exist_ok=True)
            txt.write_text(resumen(p), encoding="utf-8")
            drive.subir(txt, carpeta["id"])
            drive.carpeta("entrega", carpeta["id"])
            # ya está todo en Drive: el servidor no guarda copias de las fotos del cliente
            shutil.rmtree(pathlib.Path(cfg.datos_dir) / "subidas" / pid, ignore_errors=True)
        marca = MARCAS[p["marca"]]
        medio = p.get("pago_medio")
        recibimos = {"regalo": f"Recibimos tu pedido de regalo {p['id']}",
                     "mercadolibre": f"Recibimos los datos de tu compra de Mercado Libre (pedido {p['id']})"
                     }.get(medio, f"Recibimos el pago de tu pedido {p['id']}")
        avisos.mandar_mail(
            cfg, p["email"], f"Recibimos tu pedido {p['id']} · {marca}",
            f"¡Hola {p['nombre']}!\n\n{recibimos} "
            f"({catalogo.PRODUCTOS[p['producto']].nombre}).\n\n{_que_sigue(p)}\n\n"
            f"Si querés agregar algo, respondé este mail o escribinos por WhatsApp: https://wa.me/{cfg.whatsapp_negocio}\n\n"
            f"Gracias,\n{marca}")
        etiqueta = {"regalo": "REGALO", "mercadolibre": "MERCADO LIBRE"}.get(medio, "PAGADO")
        avisos.mandar_mail(cfg, cfg.aviso_email, f"[{etiqueta}] {p['id']} · {p['nombre']}",
                           resumen(p) + f"\n\nDrive: {p['drive_url']}", responder_a=p["email"])
        saludo = (f"¡Hola {p['nombre']}! Soy de {marca}. Recibimos tu pedido {p['id']}. "
                  f"{_que_sigue(p)}")
        titulo = {"regalo": f"🎁 Pedido de regalo {p['id']}",
                  "mercadolibre": f"Pedido de Mercado Libre {p['id']}"}.get(medio, f"Pedido pagado {p['id']}")
        avisos.avisar(cfg, titulo,
                      f"{catalogo.PRODUCTOS[p['producto']].nombre} · ${p['precio']:,} · {p['nombre']}".replace(",", "."),
                      [{"action": "view", "label": "Ver en Drive", "url": p["drive_url"]},
                       {"action": "view", "label": "WhatsApp al cliente",
                        "url": avisos.link_whatsapp(p["whatsapp"], saludo)}])
        base.actualizar(pid, error=None)
    except Exception as e:  # el pedido sigue pagado; se puede reintentar desde /admin
        log.exception("Falló al_pagar %s", pid)
        base.actualizar(pid, error=f"al_pagar: {e}"[:500])
        try:
            avisos.avisar(cfg, f"⚠ Error en {pid}", f"El pago entró pero falló Drive o el mail: {e}"[:300],
                          prioridad=5, tags=("warning",))
        except Exception:
            pass


def entregar(cfg, base, drive, pid: str, rutas: list, mensaje_extra: str = "") -> str:
    p = base.obtener(pid)
    if not p.get("drive_carpeta"):
        raise ValueError("El pedido todavía no tiene carpeta en Drive (¿está pagado?)")
    carpeta = drive.buscar_carpeta("entrega", p["drive_carpeta"]) or drive.carpeta("entrega", p["drive_carpeta"])
    for ruta in rutas:
        drive.subir(ruta, carpeta["id"])
    drive.compartir_con_link(carpeta["id"])
    link = carpeta["webViewLink"]
    base.actualizar(pid, estado="entregado", entregado=ahora(), entrega_url=link)
    p = base.obtener(pid)
    _mail_entrega(cfg, p, link, mensaje_extra)
    return link


def _mail_entrega(cfg, p: dict, link: str, mensaje_extra: str = ""):
    marca = MARCAS[p["marca"]]
    extra = f"\n\n{mensaje_extra}" if mensaje_extra else ""
    avisos.mandar_mail(
        cfg, p["email"], f"Tu pedido {p['id']} está listo · {marca}",
        f"¡Hola {p['nombre']}!\n\nTu pedido {p['id']} está listo. Lo podés descargar acá:\n{link}{extra}\n\n"
        f"El link queda disponible {DIAS_RETENCION} días: descargalo y guardalo. Después borramos todo, "
        f"incluidas las fotos que nos mandaste.\n\n"
        f"Si te gustó, nos ayuda mucho que nos recomiendes. ¡Gracias!\n{marca}")
    texto = f"¡Hola {p['nombre']}! Tu pedido {p['id']} está listo 🎁 Lo descargás acá: {link}{extra}"
    avisos.avisar(cfg, f"Entregado {p['id']}", f"Mail enviado a {p['email']}. Falta mandarle el WhatsApp.",
                  [{"action": "view", "label": "Mandar WhatsApp", "url": avisos.link_whatsapp(p["whatsapp"], texto)}],
                  prioridad=3, tags=("gift",))


def cambios_max(p: dict) -> int:
    base = 5 if catalogo.PRODUCTOS[p["producto"]].cancion else 1
    return base + (p.get("cambios_extra") or 0)


def link_revision(cfg, p: dict) -> str:
    # Con el dominio propio de la marca (https://restauraciondefotos.com.ar), el cliente revisa ahí: Nginx pasa
    # /revisar/ a la API. Si la web todavía vive bajo el campus, queda la dirección de siempre.
    web = cfg.url_web(p["marca"])
    if urllib.parse.urlparse(web).path in ("", "/"):
        base = f"{web.rstrip('/')}/revisar"
    else:
        base = cfg.url_revision or f"{cfg.url_publica}{cfg.ruta_api}/revisar"
    return f"{base}/{p['id']}?t={p['cliente_token']}"


def texto_transferencia(cfg, p: dict) -> str:
    return (f"Alias: {cfg.transferencia_alias} · CBU: {cfg.transferencia_cbu} · "
            f"Monto: ${p['precio']:,}".replace(",", ".") + f" · Pedido {p['id']}")


def aviso_sin_pago(cfg, p: dict, nota: str = ""):
    """Aviso al celular: alguien empezó un pedido y no lo pagó. Trae el WhatsApp listo para ofrecerle ayuda
    o la transferencia. `nota`: qué pasó con el mail de la foto de regalo."""
    marca = MARCAS[p["marca"]]
    prod = catalogo.PRODUCTOS[p["producto"]].nombre
    texto = (f"¡Hola {p['nombre']}! Soy de {marca}. Vi que empezaste el pedido {p['id']} ({prod}) y el pago no se "
             f"completó. ¿Te puedo ayudar? Si te resulta más fácil, también podés pagar por transferencia: "
             f"{texto_transferencia(cfg, p)}. Después mandame el comprobante por acá y lo ponemos en marcha.")
    mensaje = f"{prod} · ${p['precio']:,} · {p['nombre']} · {p['email']}".replace(",", ".")
    if nota:
        mensaje += f"\n{nota}"
    avisos.avisar(cfg, f"🛒 Pedido sin pagar {p['id']}", mensaje,
                  [{"action": "view", "label": "WhatsApp al cliente", "url": avisos.link_whatsapp(p["whatsapp"], texto)}],
                  prioridad=3, tags=("shopping_cart",))


PRODUCTO_REGALO = "rf-foto-1"     # la foto de regalo: restauración de 1 foto, digital


def link_canje(cfg, canje: dict) -> str:
    """El formulario de la web de la marca del producto, con el producto fijo y sin pago."""
    marca = catalogo.PRODUCTOS[canje["producto"]].marca
    return f"{cfg.url_web(marca).rstrip('/')}/?canje={canje['token']}"


def mail_regalo(cfg, p: dict, canje: dict):
    """A los 30 minutos sin pago: volver a intentar, transferencia o, si fue por plata, una foto de regalo."""
    marca = MARCAS[p["marca"]]
    prod = catalogo.PRODUCTOS[p["producto"]].nombre
    reintentar = f"{cfg.url_web(p['marca']).rstrip('/')}/gracias.html?pedido={p['id']}&pago=fallido"
    vence = canje["vence"][:10]
    vence = f"{vence[8:10]}/{vence[5:7]}"
    avisos.mandar_mail(
        cfg, p["email"], f"¿Pudiste completar tu pedido? · {marca}",
        f"¡Hola {p['nombre']}!\n\n"
        f"Vimos que empezaste el pedido {p['id']} ({prod}) y el pago no se completó.\n\n"
        f"Si fue un problema con el pago, podés volver a intentarlo acá:\n{reintentar}\n"
        f"o pagar por transferencia ({texto_transferencia(cfg, p)}) y mandarnos el comprobante por WhatsApp: "
        f"https://wa.me/{cfg.whatsapp_negocio}\n\n"
        f"Y si fue por un tema de plata, no te preocupes: te regalamos la restauración de una foto. "
        f"Mandala desde este formulario (es un regalo, no se cobra nada; vale hasta el {vence} y se usa una sola vez):\n"
        f"{link_canje(cfg, canje)}\n\n"
        f"{marca}\n\nSi no querés recibir más mails nuestros, respondé este mail con la palabra BAJA.")


def aviso_transferencia(cfg, p: dict):
    """Aviso al celular: el cliente eligió pagar por transferencia. Hay que mirar el comprobante en WhatsApp
    (y la plata en Mercado Pago) y recién ahí aprobarlo."""
    prod = catalogo.PRODUCTOS[p["producto"]].nombre
    avisos.avisar(cfg, f"💸 Transferencia avisada {p['id']}",
                  f"{prod} · ${p['precio']:,} · {p['nombre']}. ".replace(",", ".") +
                  f"Revisá el comprobante en WhatsApp y que la plata haya entrado. Si está todo bien, aprobalo: "
                  f"python pedidos.py transferencia {p['id']}",
                  [{"action": "view", "label": "WhatsApp al cliente",
                    "url": avisos.link_whatsapp(p["whatsapp"], f"¡Hola {p['nombre']}! Recibimos tu aviso de "
                                                               f"transferencia del pedido {p['id']}.")}],
                  prioridad=5, tags=("moneybag",))


def _mail_vista_previa(cfg, p: dict, mensaje_extra: str = ""):
    marca = MARCAS[p["marca"]]
    restantes = cambios_max(p) - (p.get("cambios") or 0)
    que = "el primer minuto de tu canción" if catalogo.PRODUCTOS[p["producto"]].cancion else "cómo quedó tu foto"
    extra = f"\n\n{mensaje_extra}" if mensaje_extra else ""
    revisar = link_revision(cfg, p)
    avisos.mandar_mail(
        cfg, p["email"], f"Mirá {que} · pedido {p['id']}",
        f"¡Hola {p['nombre']}!\n\nYa podés ver {que} (vista previa):\n{p['vista_url']}{extra}\n\n"
        f"Si te gusta, aprobala acá y te mandamos la versión final:\n{revisar}\n\n"
        f"Si querés cambiar algo, en el mismo link podés pedirlo. {quedan_cambios(restantes)}\n\n{marca}")
    texto = (f"¡Hola {p['nombre']}! Ya está la vista previa de tu pedido {p['id']}: {p['vista_url']} "
             f"Si te gusta, aprobala acá: {revisar} (ahí también podés pedir un cambio).")
    avisos.avisar(cfg, f"Vista previa enviada {p['id']}", f"Mail enviado a {p['email']}.",
                  [{"action": "view", "label": "Mandar WhatsApp", "url": avisos.link_whatsapp(p["whatsapp"], texto)},
                   {"action": "view", "label": "Ver vista previa", "url": p["vista_url"]}], prioridad=3, tags=("eyes",))


def enviar_vista_previa(cfg, base, drive, pid: str, rutas: list, mensaje_extra: str = "") -> str:
    """Sube la vista previa a Drive (carpeta compartida con link) y le pide al cliente que apruebe o pida un cambio."""
    p = base.obtener(pid)
    if not p.get("drive_carpeta"):
        raise ValueError("El pedido todavía no tiene carpeta en Drive")
    n = (p.get("vista_n") or 0) + 1
    carpeta = drive.carpeta(f"vista-previa-{n}", p["drive_carpeta"])
    for ruta in rutas:
        drive.subir(ruta, carpeta["id"])
    drive.compartir_con_link(carpeta["id"])
    base.actualizar(pid, estado="vista_previa", vista_url=carpeta["webViewLink"], vista_n=n)
    p = base.obtener(pid)
    _mail_vista_previa(cfg, p, mensaje_extra)
    return p["vista_url"]


def registrar_respuesta(cfg, base, pid: str, accion: str, texto: str = "") -> str:
    """El cliente aprueba o pide un cambio desde la página de revisión. Devuelve el estado nuevo."""
    p = base.obtener(pid)
    if accion == "aprobar":
        base.actualizar(pid, estado="aprobado", aprobado=ahora())
        avisos.avisar(cfg, f"✅ Aprobado {pid}", f"{p['nombre']} aprobó la vista previa.", prioridad=4, tags=("white_check_mark",))
        return "aprobado"
    usados = (p.get("cambios") or 0) + 1
    base.actualizar(pid, estado="cambio", cambios=usados, nota_cambio=texto[:2000])
    avisos.avisar(cfg, f"✏️ Cambio pedido {pid} ({usados}/{cambios_max(p)})", texto[:300] or "(sin detalle)",
                  prioridad=4, tags=("pencil2",))
    return "cambio"


def purgar_vencidos(cfg, base, drive, dias: int = DIAS_RETENCION) -> list:
    """Pedidos entregados hace más de `dias`: su carpeta de Drive va a la papelera y quedan marcados como purgados.
    En la base solo queda el registro de la venta (sin fotos)."""
    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    purgados = []
    for p in base.listar("entregado", limite=1000):
        if p.get("purgado") or not p.get("entregado"):
            continue
        entregado = datetime.fromisoformat(p["entregado"])
        if entregado.tzinfo is None:
            entregado = entregado.replace(tzinfo=timezone.utc)
        if entregado > limite:
            continue
        if p.get("drive_carpeta"):
            drive.papelera(p["drive_carpeta"])
        shutil.rmtree(pathlib.Path(cfg.datos_dir) / "subidas" / p["id"], ignore_errors=True)
        base.actualizar(p["id"], purgado=ahora(), archivos="[]")
        purgados.append(p["id"])
    if purgados:
        log.info("Purgados por retención (%d días): %s", dias, ", ".join(purgados))
    return purgados
