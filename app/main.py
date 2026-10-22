import calendar
import html
import json
import logging
import os
import re
import secrets
import shutil
import threading
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.datastructures import UploadFile

from . import avisos, catalogo, correo, flujo, mp, vigilante
from .config import cargar
from .db import Base, ahora
from .pagos import Pagos

log = logging.getLogger("tienda")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

FOTO_MAX_BYTES = 15 * 1024 * 1024
EXTENSIONES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff"}
URL_RE = re.compile(r"^https?://\S+$", re.I)

MESES_NOMBRES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}


def tercer_domingo(anio: int, mes: int) -> date:
    d = date(anio, mes, 1)
    dias_primer = (6 - d.weekday()) % 7
    return d + timedelta(days=dias_primer + 14)


def proxima_ocurrencia(dia: int, mes: int, hoy: date | None = None) -> tuple[date, int]:
    hoy = hoy or datetime.now(timezone(timedelta(hours=-3))).date()
    anio = hoy.year

    def fecha_en_anio(y):
        d = dia
        if mes == 2 and dia == 29 and not calendar.isleap(y):
            d = 28
        return date(y, mes, d)

    f_este = fecha_en_anio(anio)
    if f_este >= hoy:
        proxima = f_este
    else:
        proxima = fecha_en_anio(anio + 1)
    return proxima, (proxima - hoy).days



class ErrorCampo(Exception):
    def __init__(self, campo, mensaje):
        self.campo, self.mensaje = campo, mensaje


def _texto(form, campo, requerido=False, maximo=4000, minimo=0):
    v = (form.get(campo) or "").strip()
    if requerido and not v:
        raise ErrorCampo(campo, "Este dato es obligatorio.")
    if v and len(v) < minimo:
        raise ErrorCampo(campo, f"Contanos un poco más (mínimo {minimo} caracteres).")
    if len(v) > maximo:
        raise ErrorCampo(campo, f"Es demasiado largo (máximo {maximo} caracteres).")
    return v


ORIGEN_VALOR_RE = re.compile(r"^[A-Za-z0-9_.-]{1,60}$")


def _procesar_origen(raw) -> dict | None:
    if not raw:
        return None
    d = None
    if isinstance(raw, dict):
        d = raw
    elif isinstance(raw, str):
        try:
            d = json.loads(raw)
        except Exception:
            pass
    if not isinstance(d, dict):
        return None
    res = {}
    for k in ("source", "medium", "campaign", "content"):
        val = d.get(k)
        if isinstance(val, str) and ORIGEN_VALOR_RE.match(val):
            res[k] = val
    return res if res else None


def _es_imagen(cabecera: bytes, ext: str) -> bool:
    if cabecera.startswith(b"\xff\xd8\xff"):
        return True
    if cabecera.startswith(b"\x89PNG"):
        return True
    if cabecera[:4] == b"RIFF" and cabecera[8:12] == b"WEBP":
        return True
    if cabecera[4:8] == b"ftyp" and cabecera[8:12] in (b"heic", b"heix", b"mif1", b"msf1", b"heim", b"heis"):
        return True
    if cabecera[:4] in (b"II*\x00", b"MM\x00*"):
        return True
    return False


class Limitador:
    def __init__(self, maximo=12, ventana=600):
        self.maximo, self.ventana, self.registro, self.lock = maximo, ventana, {}, threading.Lock()

    def permitir(self, clave: str) -> bool:
        ahora = time.time()
        with self.lock:
            vistos = [t for t in self.registro.get(clave, []) if ahora - t < self.ventana]
            vistos.append(ahora)
            self.registro[clave] = vistos
            return len(vistos) <= self.maximo


DIAS_ANTES = 15                 # el recordatorio sale cuando faltan 15 días o menos para la fecha
DIAS_DESDE_LA_COMPRA = 30       # si compró hace menos, ese regalo ya está hecho: el aviso queda para la vez siguiente
HORA_RECORDATORIOS = 10         # hora de Argentina: los mails a clientes no salen de madrugada
HORA_AR = timezone(timedelta(hours=-3))


def revisar_recordatorios_fechas(cfg, base, hoy: date | None = None) -> list[dict]:
    """Recordatorios de fechas importantes (D-56). Solo fechas con permiso y sin baja, de pedidos cobrados.
    Sale una vez por ocurrencia, cuando faltan entre 1 y 15 días: con una ventana (y no "exactamente 15") un día con el
    servidor caído o un mail que falló no hacen perder el aviso de ese año. Si el mail falla no se marca: se reintenta."""
    hoy = hoy or datetime.now(HORA_AR).date()
    enviados = []
    for f in base.listar_fechas(solo_activas=True):
        p = base.obtener(f["pedido"]) if f.get("pedido") else None
        if not p or p["estado"] in ("pendiente_pago", "cancelado"):
            continue                                    # quien no terminó de comprar no recibe "regalale otra vez"
        dia, mes = f["dia"], f["mes"]
        proxima, faltan = proxima_ocurrencia(dia, mes, hoy)
        if not (1 <= faltan <= DIAS_ANTES) or f.get("ultimo_aviso_anio") == proxima.year:
            continue
        try:
            creado = datetime.fromisoformat(str(f.get("creado"))).astimezone(HORA_AR).date()
        except ValueError:
            creado = None
        if creado and (proxima - creado).days < DIAS_DESDE_LA_COMPRA:
            continue

        tipo_raw = f.get("tipo") or "Cumpleaños"
        tipo_txt = tipo_raw.lower() if tipo_raw != "Otra fecha" else (f.get("otra") or "fecha especial")
        dia_txt = str(proxima.day)
        mes_txt = MESES_NOMBRES.get(mes, str(mes))
        para_quien = f.get("para_quien") or "esa persona especial"
        nombre = f.get("nombre") or ""
        web_link = cfg.url_web_tc if f.get("marca") == "tc" else cfg.url_web_rf
        baja_link = f"{cfg.url_publica.rstrip('/')}/baja/{f['baja_token']}"
        saludo = f"¡Hola {nombre}!" if nombre else "¡Hola!"

        asunto = f"Se viene el {tipo_txt} de {para_quien}"
        texto_mail = (
            f"{saludo} Se viene el {tipo_txt} de {para_quien} (el {dia_txt} de {mes_txt}). "
            f"Si querés regalarle otra vez algo con su historia, acá estamos: {web_link}.\n\n"
            f"¿No querés más recordatorios? {baja_link}"
        )
        e = html.escape                                  # nombre, para quién y "otra fecha" los escribió el cliente
        html_mail = f"""<div style="font-family: sans-serif; font-size: 16px; color: #1A1712; max-width: 520px; line-height: 1.5">
<p>{e(saludo)}</p>
<p>Se viene el {e(tipo_txt)} de <b>{e(para_quien)}</b> (el {dia_txt} de {mes_txt}).</p>
<p>Si querés regalarle otra vez algo con su historia, acá estamos: <a href="{e(web_link)}" style="color: #D7301F; font-weight: 700">{e(web_link)}</a>.</p>
<hr style="border: 0; border-top: 1px solid #ddd; margin: 32px 0 16px">
<p style="font-size: 13px; color: #666">¿No querés más recordatorios? <a href="{e(baja_link)}" style="color: #666">Darte de baja acá</a>.</p>
</div>"""
        try:
            avisos.mandar_mail(cfg, f["email"], asunto, texto_mail, html=html_mail)
        except Exception as error:
            log.warning("Recordatorio de la fecha %s: no salió el mail (%s); se reintenta mañana", f["id"], error)
            continue

        texto_wa = (
            f"{saludo} Se viene el {tipo_txt} de {para_quien} (el {dia_txt} de {mes_txt}). "
            f"Si querés regalarle otra vez algo con su historia, avisame. (Si no querés que te escriba más por esto, avisame y no hay problema)."
        )
        acciones = [{"action": "view", "label": "Mandar WhatsApp", "url": avisos.link_whatsapp(f["whatsapp"], texto_wa)}]
        try:
            avisos.avisar(cfg, f"Recordatorio: {para_quien}",
                          f"En {faltan} días ({dia_txt}/{mes}) es el {tipo_txt} de {para_quien}. "
                          f"Ya le mandé el mail a {nombre or f['email']} ({f['whatsapp']}).", acciones, 4, tags=("calendar",))
        except Exception as error:
            log.warning("Recordatorio de la fecha %s: no salió el aviso por ntfy (%s)", f["id"], error)

        base.marcar_aviso_fecha(f["id"], proxima.year)
        enviados.append(f)
    return enviados


def crear_app(cfg=None, drive_factory=None, conciliar_cada: int | None = 120) -> FastAPI:
    cfg = cfg or cargar()
    cfg.datos_dir.mkdir(parents=True, exist_ok=True)
    base = Base(cfg.datos_dir / "tienda.db")
    precios_archivo = cfg.datos_dir / "precios.json"
    catalogo.cargar_precios(precios_archivo)
    estado = {"drive": None}
    limitador = Limitador()

    def avisar_proveedor(titulo, mensaje, url=None, prioridad=4):
        acciones = [{"action": "view", "label": "Ver publicación", "url": url}] if url else None
        avisos.avisar(cfg, titulo, mensaje, acciones, prioridad, tags=("shopping_cart",))
        vigilante.whatsapp(titulo, mensaje, url)

    cobros = Pagos(cfg, base)
    vigia = vigilante.Vigilante(
        cfg.datos_dir / "proveedores-estado.json", avisar_proveedor,
        vigentes=lambda: {k: p.precio for k, p in catalogo.PRODUCTOS.items()},
        ajustar=lambda prod, precio: catalogo.guardar_precios(precios_archivo, {prod: precio}),
        log=log.info, comision=cobros.comision_real)

    def drive():
        if estado["drive"] is None:
            if drive_factory:
                estado["drive"] = drive_factory()
            else:
                from .drive import Drive
                estado["drive"] = Drive(cfg.drive_token_archivo)
        return estado["drive"]

    def procesar_pago(pago_id: str, bg: BackgroundTasks | None = None):
        pago = mp.obtener_pago(cfg, pago_id)
        pid = pago.get("external_reference")
        pedido = base.obtener(pid) if pid else None
        if not pedido:
            log.warning("Pago %s sin pedido conocido (%s)", pago_id, pid)
            return
        if not mp.pago_corresponde(pago, pedido):
            log.info("Pago %s de %s: estado %s, no se marca", pago_id, pid, pago.get("status"))
            return
        if base.marcar_pagado(pid, pago_id):
            log.info("Pedido %s pagado (pago %s)", pid, pago_id)
            if bg is not None:
                bg.add_task(flujo.al_pagar, cfg, base, drive(), pid)
            else:
                flujo.al_pagar(cfg, base, drive(), pid)

    ultima_purga = {"t": 0.0}

    def conciliar():
        if time.time() - ultima_purga["t"] > 6 * 3600:      # retención: cada 6 horas alcanza
            ultima_purga["t"] = time.time()
            try:
                flujo.purgar_vencidos(cfg, base, drive())
            except Exception:
                log.exception("Falló la purga por retención")
        """Por si se pierde un webhook: revisa los pedidos pendientes de las últimas 48 h y limpia subidas viejas sin pagar."""
        ahora_utc = datetime.now(timezone.utc)
        limite = ahora_utc - timedelta(hours=48)
        for p in base.listar("pendiente_pago"):
            creado = datetime.fromisoformat(p["creado"])
            # si el cliente avisó que transfirió, se le da una semana para que llegue y se revise el comprobante
            vence = timedelta(days=7) if p.get("transferencia_avisada") else timedelta(hours=72)
            if creado < ahora_utc - vence:
                shutil.rmtree(cfg.datos_dir / "subidas" / p["id"], ignore_errors=True)
                base.actualizar(p["id"], estado="cancelado", error="vencido sin pago")
                continue
            pagos, mp_respondio = [], False
            if creado >= limite:
                try:
                    pagos = mp.pagos_de_pedido(cfg, p["id"])
                    mp_respondio = True
                except Exception as e:
                    log.warning("Conciliación %s: %s", p["id"], e)
                aprobado = next((x for x in pagos if x.get("status") == "approved"), None)
                if aprobado:
                    procesar_pago(str(aprobado["id"]))
                    if base.obtener(p["id"])["estado"] != "pendiente_pago":
                        continue
            if p.get("transferencia_avisada") or creado >= ahora_utc - timedelta(minutes=cfg.minutos_aviso_sin_pago):
                continue
            # A los 30 minutos sin pago: mail con la foto de regalo y aviso al celular
            en_curso = [x for x in pagos if x.get("status") in ("pending", "in_process", "authorized")]
            nota = ""
            if not p.get("regalo_enviado"):
                if en_curso:     # pagó en efectivo (Rapipago / Pago Fácil) y se acredita en horas: el regalo espera
                    nota = "Tiene un pago en efectivo pendiente: el mail con la foto de regalo espera a ver si se acredita."
                elif not mp_respondio and creado >= limite:
                    nota = "Mercado Pago no respondió: el mail con la foto de regalo se manda en la próxima vuelta."
                elif base.regalo_dado(p["email"], p["whatsapp"]):
                    base.actualizar(p["id"], regalo_enviado="no: ya recibió una foto de regalo antes")
                    nota = "No se le mandó la foto de regalo: ya recibió una antes (mismo mail o WhatsApp)."
                else:
                    vence = (ahora_utc + timedelta(days=14)).isoformat(timespec="seconds")
                    cj = base.crear_canje(token=secrets.token_urlsafe(16), tipo="regalo", producto=flujo.PRODUCTO_REGALO,
                                          vence=vence, email=p["email"], whatsapp=p["whatsapp"], origen=p["id"])
                    base.actualizar(p["id"], regalo_enviado=ahora())   # primero se marca: nunca manda dos mails
                    try:
                        flujo.mail_regalo(cfg, p, cj)
                        nota = "Se le mandó el mail con la foto de regalo."
                    except Exception as e:
                        log.warning("Mail de regalo %s: %s", p["id"], e)
                        nota = f"No salió el mail de la foto de regalo: {e}"[:200]
            if not p.get("aviso_sin_pago"):
                base.actualizar(p["id"], aviso_sin_pago=ahora())      # primero se marca: nunca avisa dos veces
                try:
                    flujo.aviso_sin_pago(cfg, base.obtener(p["id"]), nota)
                except Exception as e:
                    log.warning("Aviso de pedido sin pagar %s: %s", p["id"], e)

    ultima_recordatorios = {"dia": None}

    def revisar_recordatorios():
        ahora_ar = datetime.now(HORA_AR)
        hoy = ahora_ar.date()
        if ahora_ar.hour < HORA_RECORDATORIOS:          # no se manda nada de madrugada
            return
        if ultima_recordatorios["dia"] != hoy:
            try:
                revisar_recordatorios_fechas(cfg, base, hoy)
                ultima_recordatorios["dia"] = hoy
            except Exception:
                log.exception("Falló el recordatorio diario de fechas")

    def bucle():
        while True:
            time.sleep(conciliar_cada)
            try:
                conciliar()
            except Exception:
                log.exception("Falló la conciliación")
            try:
                vigia.revisar()                       # cada 30 min: precio y envío de los cuadros de proveedores
            except Exception:
                log.exception("Falló el vigilante de proveedores")
            try:
                revisar_recordatorios()
            except Exception:
                log.exception("Falló la revisión de recordatorios")

    @asynccontextmanager
    async def ciclo(app):
        if conciliar_cada:
            threading.Thread(target=bucle, daemon=True).start()
        yield

    app = FastAPI(title="Tienda Tu Canción · Restauración de fotos", root_path=cfg.ruta_api, lifespan=ciclo,
                  docs_url=None, redoc_url=None, openapi_url=None)
    origenes = [o.strip() for o in os.environ.get("CORS_ORIGENES", "").split(",") if o.strip()]
    if origenes:
        app.add_middleware(CORSMiddleware, allow_origins=origenes, allow_methods=["GET", "POST"], allow_headers=["*"])
    app.state.base, app.state.cfg, app.state.conciliar = base, cfg, conciliar
    app.state.cobros = cobros
    app.state.vigia = vigia
    app.state.revisar_recordatorios_fechas = lambda hoy=None: revisar_recordatorios_fechas(cfg, base, hoy)



    @app.exception_handler(ErrorCampo)
    async def _error_campo(request, e: ErrorCampo):
        return JSONResponse({"error": e.mensaje, "campo": e.campo}, status_code=422)

    @app.get("/salud")
    def salud():
        return {"ok": True, "modo": cfg.mp_modo}

    @app.get("/catalogo")
    def ver_catalogo(marca: str | None = None):
        return {"productos": catalogo.activos(marca), "estilos": catalogo.ESTILOS, "voces": catalogo.VOCES,
                "duraciones": catalogo.DURACIONES, "whatsapp": cfg.whatsapp_negocio,
                "transferencia": {"alias": cfg.transferencia_alias, "cbu": cfg.transferencia_cbu}}

    @app.get("/canje/{token}")
    def ver_canje(token: str):
        """Para que la web arme el formulario sin pago: qué producto es y si el link sirve."""
        cj = base.obtener_canje(token)
        if not cj:
            raise HTTPException(404, "Este link no existe. Escribinos por WhatsApp.")
        prod = catalogo.PRODUCTOS[cj["producto"]]
        estado_cj = "usado" if cj["usado"] else ("vencido" if cj["vence"] < ahora() else "valido")
        return {"estado": estado_cj, "tipo": cj["tipo"], "producto": prod.id, "nombre": prod.nombre, "marca": prod.marca}

    @app.post("/pedidos", status_code=201)
    async def crear_pedido(request: Request, bg: BackgroundTasks):
        ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "?")
        if not limitador.permitir(ip):
            return JSONResponse({"error": "Demasiados intentos. Probá de nuevo en unos minutos."}, status_code=429)
        form = await request.form(max_files=25, max_fields=60, max_part_size=1024 * 1024)
        if (form.get("sitio_web") or "").strip():          # trampa para bots
            raise ErrorCampo("sitio_web", "Pedido inválido.")
        # Link de un solo uso (foto de regalo o compra hecha en Mercado Libre): el producto lo fija el link y no se cobra
        token_canje = (form.get("canje") or "").strip()
        canje = None
        if token_canje:
            canje = base.obtener_canje(token_canje)
            if not canje or canje["usado"] or canje["vence"] < ahora():
                raise ErrorCampo("canje", "Este link ya se usó o venció. Escribinos por WhatsApp y lo resolvemos.")
            prod = catalogo.PRODUCTOS.get(canje["producto"])
        else:
            prod = catalogo.PRODUCTOS.get(form.get("producto") or "")
        if not prod or not prod.activo:
            raise ErrorCampo("producto", "Elegí un producto de la lista.")
        nombre = _texto(form, "nombre", True, 120)
        email = _texto(form, "email", True, 200)
        error_mail = correo.problema(email, revisado=form.get("email_revisado") == "si")
        if error_mail:
            raise ErrorCampo("email", error_mail)
        usuario, _, dominio = email.rpartition("@")
        email = f"{usuario}@{dominio.lower()}"
        whatsapp = avisos.normalizar_whatsapp(_texto(form, "whatsapp", True, 40))
        if not (12 <= len(whatsapp) <= 15):
            raise ErrorCampo("whatsapp", "Revisá el WhatsApp: código de área y número, sin 0 ni 15.")
        if (form.get("acepto") or "") not in ("si", "on", "true", "1"):
            raise ErrorCampo("acepto", "Tenés que aceptar las condiciones para seguir.")
        datos = {"comentarios": _texto(form, "comentarios", maximo=3000)}
        if prod.marca == "rf" or prod.fotos_max:
            datos["color"] = _texto(form, "color", maximo=60)
        if prod.cancion:
            estilos = [e for e in form.getlist("estilos") if e in catalogo.ESTILOS]
            if not estilos:
                raise ErrorCampo("estilos", "Elegí al menos un estilo.")
            voz = form.get("voz") or ""
            if voz not in catalogo.VOCES:
                raise ErrorCampo("voz", "Elegí el tipo de voz.")
            duracion = form.get("duracion") or ""
            if duracion not in catalogo.DURACIONES:
                raise ErrorCampo("duracion", "Elegí la duración.")
            inspiracion = _texto(form, "inspiracion", maximo=500)
            if inspiracion and not URL_RE.match(inspiracion):
                raise ErrorCampo("inspiracion", "Pegá el link completo (empieza con https://).")
            datos.update({
                "para_quien": _texto(form, "para_quien", True, 120),
                "vinculo": _texto(form, "vinculo", maximo=120),
                "ocasion": _texto(form, "ocasion", maximo=120),
                "estilos": estilos, "estilo_otro": _texto(form, "estilo_otro", maximo=120),
                "voz": voz, "inspiracion": inspiracion,
                "historia": _texto(form, "historia", True, 6000, minimo=40),
                "evitar": _texto(form, "evitar", maximo=1000), "duracion": duracion,
            })
        if prod.envio:
            datos["envio"] = {
                "destinatario": _texto(form, "envio_destinatario", maximo=120) or nombre,
                "calle": _texto(form, "envio_calle", True, 120), "numero": _texto(form, "envio_numero", True, 20),
                "piso_depto": _texto(form, "envio_piso", maximo=40),
                "localidad": _texto(form, "envio_localidad", True, 80),
                "provincia": _texto(form, "envio_provincia", True, 60), "cp": _texto(form, "envio_cp", True, 10),
                "dni": _texto(form, "envio_dni", True, 12),
            }
        if prod.marcos:
            marco = form.get("marco") or ""
            if marco not in prod.marcos:
                raise ErrorCampo("marco", "Elegí el color del marco.")
            datos["marco"] = marco

        fecha_permiso = (form.get("fecha_permiso") or "").strip().lower()
        fecha_dia_raw = form.get("fecha_dia")
        fecha_mes_raw = form.get("fecha_mes")
        fecha_tipo_raw = (form.get("fecha_tipo") or "").strip()
        fecha_otra_raw = _texto(form, "fecha_otra", maximo=40)

        fecha_a_guardar = None
        tiene_datos_fecha = bool(fecha_dia_raw or fecha_mes_raw or (fecha_tipo_raw and fecha_tipo_raw != "null"))

        if fecha_permiso in ("si", "1", "true", "on") or tiene_datos_fecha:
            if not fecha_dia_raw or not str(fecha_dia_raw).isdigit():
                if fecha_permiso in ("si", "1", "true", "on"):
                    raise ErrorCampo("fecha_dia", "Elegí el día.")
            if not fecha_mes_raw or not str(fecha_mes_raw).isdigit():
                if fecha_permiso in ("si", "1", "true", "on"):
                    raise ErrorCampo("fecha_mes", "Elegí el mes.")

            if fecha_dia_raw and str(fecha_dia_raw).isdigit() and fecha_mes_raw and str(fecha_mes_raw).isdigit():
                f_dia = int(fecha_dia_raw)
                f_mes = int(fecha_mes_raw)
                if not (1 <= f_mes <= 12):
                    raise ErrorCampo("fecha_mes", "El mes debe estar entre 1 y 12.")
                max_dias = 30 if f_mes in (4, 6, 9, 11) else (29 if f_mes == 2 else 31)
                if not (1 <= f_dia <= max_dias):
                    raise ErrorCampo("fecha_dia", f"El día {f_dia} no existe para el mes elegido.")

                if not fecha_tipo_raw:
                    if fecha_permiso in ("si", "1", "true", "on"):
                        raise ErrorCampo("fecha_tipo", "Elegí qué tipo de fecha es.")
                else:
                    tipos_validos = {"cumpleaños", "cumpleanos", "aniversario", "otra fecha", "otra"}
                    if fecha_tipo_raw.lower() not in tipos_validos:
                        raise ErrorCampo("fecha_tipo", "Elegí un tipo de fecha válido.")

                    f_tipo = "Cumpleaños" if "cumple" in fecha_tipo_raw.lower() else ("Aniversario" if "aniv" in fecha_tipo_raw.lower() else "Otra fecha")
                    if f_tipo == "Otra fecha" and len(fecha_otra_raw) > 40:
                        raise ErrorCampo("fecha_otra", "La descripción de la fecha no puede tener más de 40 caracteres.")

                    if fecha_permiso in ("si", "1", "true", "on"):
                        fecha_a_guardar = {
                            "dia": f_dia,
                            "mes": f_mes,
                            "tipo": f_tipo,
                            "otra": fecha_otra_raw if f_tipo == "Otra fecha" else "",
                        }

        fotos = [f for f in form.getlist("fotos") if isinstance(f, UploadFile) and f.filename]
        if prod.fotos_max:
            if len(fotos) < prod.fotos_min:
                raise ErrorCampo("fotos", "Adjuntá la foto.")
            if len(fotos) > prod.fotos_max:
                raise ErrorCampo("fotos", f"Este producto lleva hasta {prod.fotos_max} fotos.")
        elif fotos:
            raise ErrorCampo("fotos", "Este producto no lleva fotos.")
        for f in fotos:
            ext = os.path.splitext(f.filename)[1].lower()
            if ext not in EXTENSIONES:
                raise ErrorCampo("fotos", f"{f.filename}: subí la foto en JPG, PNG, WEBP o HEIC.")

        # Origen / UTM (Tarea 18)
        origen_raw = form.get("origen")
        if not origen_raw:
            src = form.get("utm_source") or form.get("source")
            med = form.get("utm_medium") or form.get("medium")
            cam = form.get("utm_campaign") or form.get("campaign")
            cnt = form.get("utm_content") or form.get("content")
            if any((src, med, cam, cnt)):
                origen_raw = {"source": src, "medium": med, "campaign": cam, "content": cnt}
        origen_valido = _procesar_origen(origen_raw)
        if origen_valido:
            datos["origen"] = origen_valido

        pid = base.nuevo_id(prod.marca)
        carpeta = cfg.datos_dir / "subidas" / pid
        rutas = []
        try:
            carpeta.mkdir(parents=True, exist_ok=True)
            historial_file = carpeta / "historial.txt"
            lineas_h = [f"[{datetime.now().strftime('%d/%m/%Y %H:%M')}] Pedido {pid} creado ({prod.nombre})"]
            if origen_valido:
                orig_str = " · ".join(f"{k}: {v}" for k, v in origen_valido.items())
                lineas_h.append(f"    Origen: {orig_str}")
            historial_file.write_text("\n".join(lineas_h) + "\n", encoding="utf-8")

            for i, f in enumerate(fotos, 1):
                ext = os.path.splitext(f.filename)[1].lower().replace(".jpeg", ".jpg")
                ruta = carpeta / f"foto-{i:02d}{ext}"
                total, cabecera = 0, b""
                with open(ruta, "wb") as out:
                    while bloque := await f.read(1024 * 1024):
                        if not cabecera:
                            cabecera = bloque[:16]
                        total += len(bloque)
                        if total > FOTO_MAX_BYTES:
                            raise ErrorCampo("fotos", f"{f.filename} pesa más de 15 MB.")
                        out.write(bloque)
                if not _es_imagen(cabecera, ext):
                    raise ErrorCampo("fotos", f"{f.filename} no parece una foto.")
                rutas.append(str(ruta))
            extra = {"canje": token_canje} if canje else {}
            pedido = base.crear(id=pid, marca=prod.marca, producto=prod.id, precio=0 if canje else prod.precio,
                                nombre=nombre, email=email, whatsapp=whatsapp, datos=datos, archivos=rutas,
                                cliente_token=secrets.token_urlsafe(18), **extra)
            if fecha_a_guardar:
                p_quien = datos.get("para_quien") or _texto(form, "para_quien", maximo=120) or nombre
                vinc = datos.get("vinculo") or _texto(form, "vinculo", maximo=120) or ""
                base.guardar_fecha(
                    pedido=pid,
                    nombre=nombre,
                    email=email,
                    whatsapp=whatsapp,
                    marca=prod.marca,
                    para_quien=p_quien,
                    vinculo=vinc,
                    tipo=fecha_a_guardar["tipo"],
                    otra=fecha_a_guardar["otra"],
                    dia=fecha_a_guardar["dia"],
                    mes=fecha_a_guardar["mes"],
                    permiso_en=ahora(),
                    permiso_texto="v1",
                    baja_token=secrets.token_urlsafe(24),
                )
            if canje:
                if not base.usar_canje(token_canje, pid):           # dos envíos a la vez con el mismo link
                    base.actualizar(pid, estado="cancelado", error="link de un solo uso ya usado")
                    raise ErrorCampo("canje", "Este link ya se usó. Escribinos por WhatsApp y lo resolvemos.")
                base.marcar_pagado_canje(pid, canje["tipo"])
                bg.add_task(flujo.al_pagar, cfg, base, drive(), pid)
                return {"pedido": pid, "precio": 0, "producto": prod.nombre, "pagado": True}
            pref = mp.crear_preferencia(cfg, pedido, prod)

        except ErrorCampo:
            shutil.rmtree(carpeta, ignore_errors=True)
            raise
        except Exception as e:   # ErrorMP, red caída, encabezado inválido…: el cliente nunca ve un 500 mudo
            log.exception("No se pudo crear la preferencia de %s", pid)
            base.actualizar(pid, estado="cancelado", error=str(e)[:500])
            try:   # alguien quiso comprar y no pudo: que te enteres
                p_err = base.obtener(pid)
                if p_err:
                    avisos.avisar(cfg, f"⚠ No se pudo crear el pago de {pid}",
                                  f"{p_err['nombre']} · {p_err['email']}: Mercado Pago no respondió.",
                                  prioridad=5, tags=("warning",))
            except Exception:
                pass
            return JSONResponse({"error": "No pudimos conectar con Mercado Pago. Probá de nuevo en un rato "
                                          "o escribinos por WhatsApp."}, status_code=502)
        base.actualizar(pid, mp_preferencia=pref.get("id"), mp_init_point=pref.get("init_point"))
        return {"pedido": pid, "precio": prod.precio, "producto": prod.nombre, "init_point": pref["init_point"]}

    @app.get("/pedidos/{pid}/estado")
    def estado_pedido(pid: str):
        p = base.obtener(pid.upper())
        if not p:
            raise HTTPException(404, "No encontramos ese pedido.")
        return {"pedido": p["id"], "estado": p["estado"], "producto": catalogo.PRODUCTOS[p["producto"]].nombre,
                "marca": p["marca"], "precio": p["precio"],     # precio: el valor de la compra para el píxel
                "transferencia_avisada": bool(p.get("transferencia_avisada")), "pago_medio": p.get("pago_medio")}

    @app.get("/pedidos/{pid}/pagar")
    def volver_a_pagar(pid: str):
        """El link de Mercado Pago del mismo pedido, para reintentar sin volver a llenar el formulario."""
        p = base.obtener(pid.upper())
        if not p:
            raise HTTPException(404, "No encontramos ese pedido.")
        if p["estado"] != "pendiente_pago":
            raise HTTPException(409, "Este pedido ya no está esperando el pago.")
        link = p.get("mp_init_point")
        if not link:     # pedidos anteriores a este cambio: se pide la preferencia de nuevo (misma clave, no duplica)
            try:
                pref = mp.crear_preferencia(cfg, p, catalogo.PRODUCTOS[p["producto"]])
            except Exception:
                log.exception("No se pudo recrear la preferencia de %s", p["id"])
                return JSONResponse({"error": "No pudimos conectar con Mercado Pago. Probá de nuevo en un rato "
                                              "o pagá por transferencia."}, status_code=502)
            link = pref.get("init_point")
            base.actualizar(p["id"], mp_preferencia=pref.get("id"), mp_init_point=link)
        return {"pedido": p["id"], "init_point": link}

    @app.post("/pedidos/{pid}/transferencia")
    def avisar_transferencia(pid: str, request: Request):
        """El cliente eligió pagar por transferencia: te avisa al celular (una sola vez por pedido) para que mires
        el comprobante. El pedido sigue esperando el pago hasta que lo apruebes."""
        ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "?")
        if not limitador.permitir(ip):
            return JSONResponse({"error": "Demasiados intentos. Probá de nuevo en unos minutos."}, status_code=429)
        p = base.obtener(pid.upper())
        if not p:
            raise HTTPException(404, "No encontramos ese pedido.")
        if p["estado"] != "pendiente_pago":
            raise HTTPException(409, "Este pedido ya no está esperando el pago.")
        if not p.get("transferencia_avisada"):
            base.actualizar(p["id"], transferencia_avisada=ahora())
            try:
                flujo.aviso_transferencia(cfg, base.obtener(p["id"]))
            except Exception as e:
                log.warning("Aviso de transferencia %s: %s", p["id"], e)
        return {"ok": True, "pedido": p["id"], "monto": p["precio"],
                "alias": cfg.transferencia_alias, "cbu": cfg.transferencia_cbu}

    @app.post("/mp/webhook")
    async def webhook(request: Request, bg: BackgroundTasks, x_signature: str | None = Header(None),
                      x_request_id: str | None = Header(None)):
        q = request.query_params
        try:
            cuerpo = await request.json()
        except Exception:
            cuerpo = {}
        tipo = q.get("type") or q.get("topic") or cuerpo.get("type")
        data_id = q.get("data.id") or q.get("id") or str((cuerpo.get("data") or {}).get("id") or "")
        if cfg.mp_webhook_secret and not mp.firma_valida(cfg.mp_webhook_secret, x_signature, x_request_id, q.get("data.id")):
            log.warning("Webhook con firma inválida (data.id=%s)", data_id)
            return JSONResponse({"ok": False}, status_code=401)
        if tipo == "payment" and data_id:
            try:
                procesar_pago(data_id, bg)
            except mp.ErrorMP as e:
                log.error("Webhook pago %s: %s", data_id, e)
                return JSONResponse({"ok": False}, status_code=500)   # Mercado Pago reintenta
        return {"ok": True}

    # ---- retorno de la autorización de la API de Mercado Libre (el vigilante de la PC pide el código) ----
    @app.post("/ml/notificaciones")
    def ml_notificaciones():
        """Por si la app de ML exige una URL de notificaciones: se aceptan y se ignoran (el vigilante consulta solo)."""
        return {"ok": True}

    @app.get("/ml/callback", response_class=HTMLResponse)
    def ml_callback(code: str = "", error: str = "", error_description: str = ""):
        """No guarda nada: muestra el código para que lo pegues en la PC (python ml_api.py autorizar)."""
        if not re.fullmatch(r"[A-Za-z0-9_\-.]{8,200}", code or ""):
            cuerpo = (f"<h1>No llegó el permiso</h1><p>{html.escape(error_description or error or 'Falta el código.')}</p>"
                      "<p>Volvé a correr en la PC: <code>python ml_api.py autorizar</code></p>")
        else:
            cuerpo = (f"<h1>Listo, falta un paso</h1><p>Copiá este código y pegalo en la ventana de la PC "
                      f"(dura unos minutos):</p><p><input id=c readonly value=\"{html.escape(code)}\" "
                      "onclick=\"this.select()\"> <button onclick=\"navigator.clipboard.writeText(c.value);"
                      "this.textContent='Copiado'\">Copiar</button></p>")
        return HTMLResponse(f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Mercado Libre · tutienditaia</title>
<style>body{{margin:0;background:#FFFAEB;color:#1A1712;font:17px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,system-ui,sans-serif;padding:32px 16px}}
main{{max-width:560px;margin:0 auto}} input{{width:100%;box-sizing:border-box;font:16px monospace;padding:10px;
border:2px solid #1A1712;border-radius:6px}} button{{margin-top:8px;font-weight:700;font-size:17px;font-family:inherit;min-height:48px;padding:0 18px;border:0;
border-radius:6px;background:#D7301F;color:#fff;cursor:pointer}}</style></head><body><main>{cuerpo}</main></body></html>""",
                            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})

    # ---- administración (Authorization: Bearer TIENDA_ADMIN_TOKEN) ----
    def _admin(authorization: str | None):
        if not cfg.admin_token or authorization != f"Bearer {cfg.admin_token}":
            raise HTTPException(401, "No autorizado")

    @app.get("/admin/pedidos")
    def admin_pedidos(estado: str | None = None, authorization: str | None = Header(None)):
        _admin(authorization)
        return [{k: p.get(k) for k in ("id", "estado", "producto", "precio", "nombre", "email", "whatsapp", "creado",
                                       "pagado", "drive_url", "vista_url", "vista_n", "cambios", "nota_cambio",
                                       "aprobado", "entrega_url", "error", "cambios_extra", "entregado", "marca",
                                       "seguimiento", "seguimiento_url", "cuadro_comprado", "pago_medio",
                                       "aviso_sin_pago", "transferencia_avisada", "canje", "regalo_enviado")}
                for p in base.listar(estado)]

    @app.post("/admin/canjes")
    async def admin_crear_canje(request: Request, authorization: str | None = Header(None)):
        """Link de un solo uso al formulario sin pago. Mercado Libre: {"tipo": "mercadolibre", "producto", "orden"}
        (un link por orden; si ya hay uno sin usar, devuelve ese). Regalo a mano: {"tipo": "regalo", "email", "whatsapp"}."""
        _admin(authorization)
        d = await request.json()
        tipo = d.get("tipo")
        if tipo not in ("mercadolibre", "regalo"):
            raise HTTPException(422, "tipo: mercadolibre o regalo")
        prod = catalogo.PRODUCTOS.get(d.get("producto") or (flujo.PRODUCTO_REGALO if tipo == "regalo" else ""))
        if not prod or not prod.activo:
            raise HTTPException(422, "Producto desconocido o inactivo")
        if prod.envio and tipo == "mercadolibre":
            raise HTTPException(422, "Los cuadros vendidos en Mercado Libre se despachan con la etiqueta de ML: "
                                     "la foto se pide por el chat de ML, no con este formulario.")
        origen = str(d.get("orden") or "").strip()
        if tipo == "mercadolibre":
            if not origen.isdigit():
                raise HTTPException(422, "Falta el número de orden de Mercado Libre")
            previo = base.canje_de_orden("mercadolibre", origen)
            if previo and not previo["usado"] and previo["vence"] >= ahora():
                return {**previo, "link": flujo.link_canje(cfg, previo), "nuevo": False}
        dias = 30 if tipo == "mercadolibre" else 14
        vence = (datetime.now(timezone.utc) + timedelta(days=dias)).isoformat(timespec="seconds")
        cj = base.crear_canje(token=secrets.token_urlsafe(16), tipo=tipo, producto=prod.id, vence=vence,
                              email=d.get("email") or None, whatsapp=d.get("whatsapp") or None, origen=origen or None)
        return {**cj, "link": flujo.link_canje(cfg, cj), "nuevo": True}

    @app.get("/admin/interesados")
    def admin_interesados(authorization: str | None = Header(None)):
        """Quienes empezaron un pedido y no lo pagaron (uno por mail, sin los que después compraron)."""
        _admin(authorization)
        return base.interesados()

    @app.get("/admin/proveedores")
    def admin_proveedores(authorization: str | None = Header(None)):
        _admin(authorization)
        return vigia.datos_admin()

    @app.post("/admin/proveedores/{nombre}/precio")
    async def admin_fijar_precio_a_mano(nombre: str, request: Request, authorization: str | None = Header(None)):
        _admin(authorization)
        try:
            datos = await request.json()
            if not isinstance(datos, dict) or "precio" not in datos:
                raise HTTPException(422, "Mandá un JSON con {'precio': int}")
            precio = datos.get("precio")
            if not isinstance(precio, int) or isinstance(precio, bool) or not (1 <= precio <= 10_000_000):
                raise HTTPException(422, "El precio debe ser un número entero entre 1 y 10.000.000")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(422, "JSON inválido")
        try:
            res = vigia.fijar_precio_a_mano(nombre, precio)
        except KeyError:
            raise HTTPException(404, f"No existe la publicación {nombre}")
        except ValueError as e:
            raise HTTPException(422, str(e))
        return {"ok": True, "nombre": nombre, "a_mano": res}

    @app.delete("/admin/proveedores/{nombre}/precio")
    def admin_quitar_precio_a_mano(nombre: str, authorization: str | None = Header(None)):
        _admin(authorization)
        try:
            quitado = vigia.quitar_precio_a_mano(nombre)
        except KeyError:
            raise HTTPException(404, f"No existe la publicación {nombre}")
        return {"ok": True, "nombre": nombre, "quitado": quitado}

    @app.post("/admin/proveedores/pendientes/{producto}/aprobar")
    def admin_aprobar_pendiente(producto: str, authorization: str | None = Header(None)):
        _admin(authorization)
        res = vigia.aprobar_pendiente(producto)
        if not res:
            raise HTTPException(404, f"No hay cambio pendiente para el producto {producto}")
        return {"ok": True, "producto": producto, "aplicado": res}

    @app.post("/admin/proveedores/pendientes/{producto}/rechazar")
    def admin_rechazar_pendiente(producto: str, authorization: str | None = Header(None)):
        _admin(authorization)
        res = vigia.rechazar_pendiente(producto)
        if not res:
            raise HTTPException(404, f"No hay cambio pendiente para el producto {producto}")
        return {"ok": True, "producto": producto, "rechazado": res}


    @app.get("/admin/pagos")
    def admin_pagos(desde: str | None = None, authorization: str | None = Header(None)):
        """Cobros de MP de cada pedido, con lista blanca de campos (nada del pagador). Ver pagos.py."""
        _admin(authorization)
        return cobros.lista(desde)

    @app.get("/admin/costos")
    def admin_costos(authorization: str | None = Header(None)):
        _admin(authorization)
        productos = {k: {"nombre": p.nombre, "precio": p.precio} for k, p in catalogo.PRODUCTOS.items()}

        ruta_vig = cfg.datos_dir / "proveedores-estado.json"
        leido_iso = None
        estado_costos = {}
        a_mano = {}
        comision_mp = None
        if ruta_vig.is_file():
            try:
                mtime_dt = datetime.fromtimestamp(ruta_vig.stat().st_mtime, tz=timezone.utc)
                leido_iso = mtime_dt.isoformat()
                estado_json = json.loads(ruta_vig.read_text(encoding="utf-8"))
                estado_costos = estado_json.get("costos", {})
                comision_mp = estado_json.get("comision_mp")   # la que usó el vigilante para los precios (D-49)
                a_mano = estado_json.get("a_mano", {})          # precios cargados a mano (los usa el vigilante)
            except Exception:
                pass

        publicaciones = []
        try:
            for pub in vigilante.publicaciones():
                nombre_pub = pub.get("nombre")
                costo_pub = estado_costos.get(nombre_pub) if estado_costos else None
                publicaciones.append({
                    "producto": pub.get("producto"),
                    "nombre": nombre_pub,
                    "url": pub.get("url"),
                    "publicado": costo_pub,
                    "a_mano": (a_mano.get(nombre_pub) or {}).get("precio"),
                })
        except Exception:
            pass

        return {
            "productos": productos,
            "proveedores": {
                "leido": leido_iso,
                "publicaciones": publicaciones,
            },
            "comision_mp": comision_mp,
        }

    def _info_producto_precio(prod_id: str) -> dict:
        prod = catalogo.PRODUCTOS[prod_id]
        cfg_prov = vigilante.config()
        es_cuadro = prod_id in cfg_prov.get("productos", {})
        modo_info = vigia.modo(prod_id) if es_cuadro else {}
        regla = cfg_prov.get("productos", {}).get(prod_id, {})
        ganancia_a_mano = modo_info.get("ganancia_neta")
        ganancia_neta = ganancia_a_mano if ganancia_a_mano is not None else regla.get("ganancia_neta")
        ganancia_origen = "a mano" if ganancia_a_mano is not None else ("regla" if es_cuadro else None)
        return {
            "id": prod.id,
            "nombre": prod.nombre,
            "marca": prod.marca,
            "precio": prod.precio,
            "con_proveedor": es_cuadro,
            "modo": modo_info.get("modo", "auto") if es_cuadro else None,
            "ganancia_neta": ganancia_neta,
            "ganancia_origen": ganancia_origen,
        }

    @app.get("/admin/precios")
    def admin_listar_precios(authorization: str | None = Header(None)):
        _admin(authorization)
        productos = [_info_producto_precio(pid) for pid in catalogo.PRODUCTOS]
        historial = vigia.historial_precios(50)
        return {"productos": productos, "historial": historial}

    @app.post("/admin/precios/{producto}")
    async def admin_cambiar_precio_producto(producto: str, request: Request, authorization: str | None = Header(None)):
        _admin(authorization)
        if producto not in catalogo.PRODUCTOS:
            raise HTTPException(404, f"No existe el producto {producto}")
        try:
            body = await request.json()
            if not isinstance(body, dict):
                return JSONResponse({"error": "JSON inválido", "campo": "precio"}, status_code=422)
        except Exception:
            return JSONResponse({"error": "JSON inválido", "campo": "precio"}, status_code=422)

        cfg_prov = vigilante.config()
        es_cuadro = producto in cfg_prov.get("productos", {})

        if "precio" in body:
            precio = body.get("precio")
            if not isinstance(precio, int) or isinstance(precio, bool) or not (100 <= precio <= 1_000_000):
                return JSONResponse({"error": "El precio debe ser un número entero entre 100 y 1.000.000", "campo": "precio"}, status_code=422)
            # Con el candado del vigilante: si justo está revisando, espera; si no, podría pisar el precio recién puesto
            with vigia._candado:
                if es_cuadro:
                    vigia.fijar_modo(producto, "fijo", None)
                antes = catalogo.PRODUCTOS[producto].precio
                catalogo.guardar_precios(precios_archivo, {producto: precio})
                vigilante.registrar_historial_precio(vigia.ruta_historial, producto, antes, precio, "a mano")
            return _info_producto_precio(producto)

        elif "modo" in body:
            if not es_cuadro:
                return JSONResponse({"error": "El modo automático solo aplica a productos con proveedor (cuadros)", "campo": "modo"}, status_code=422)
            modo = body.get("modo")
            if modo != "auto":
                return JSONResponse({"error": "Modo inválido. Usá 'auto'", "campo": "modo"}, status_code=422)
            ganancia_neta = body.get("ganancia_neta")
            if ganancia_neta is not None:
                if not isinstance(ganancia_neta, int) or isinstance(ganancia_neta, bool) or not (0 <= ganancia_neta <= 1_000_000):
                    return JSONResponse({"error": "La ganancia neta debe ser un entero entre 0 y 1.000.000 o null", "campo": "ganancia_neta"}, status_code=422)
            vigia.fijar_modo(producto, "auto", ganancia_neta)
            try:
                vigia.recalcular_producto(producto)
            except Exception as e:
                return JSONResponse({"error": f"No se pudo recalcular el precio: {e}", "campo": "modo"}, status_code=422)
            return _info_producto_precio(producto)

        else:
            return JSONResponse({"error": "Mandá 'precio' o 'modo'", "campo": "precio"}, status_code=422)

    @app.post("/admin/precios")
    async def admin_precios(request: Request, authorization: str | None = Header(None)):
        """{"rf-cuadro-ecocuero-20x30": 35900, ...}: cambia precios sin reiniciar (los pedidos ya creados no cambian)."""
        _admin(authorization)
        try:
            pedido = {str(k): int(v) for k, v in (await request.json()).items()}
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(400, "Mandá un objeto {producto: precio en pesos}.")
        malos = [k for k, v in pedido.items() if k not in catalogo.BASE or not 100 <= v <= 1_000_000]
        if malos or not pedido:
            raise HTTPException(400, f"Producto o precio inválido: {', '.join(malos) or 'vacío'}")
        antes_dict = {k: catalogo.PRODUCTOS[k].precio for k in pedido}
        ajustes = catalogo.guardar_precios(precios_archivo, pedido)
        for k, v in pedido.items():
            vigilante.registrar_historial_precio(vigia.ruta_historial, k, antes_dict.get(k, 0), v, "a mano")
        log.info("Precios ajustados: %s", pedido)
        return {"ajustes": ajustes, "precios": {k: p.precio for k, p in catalogo.PRODUCTOS.items()}}

    @app.get("/admin/fechas")
    def admin_fechas(authorization: str | None = Header(None)):
        _admin(authorization)
        hoy = datetime.now(HORA_AR).date()
        # Solo fechas de pedidos cobrados: quien no terminó de comprar no cuenta como contacto (ni recibe recordatorios)
        cobrados = {p["id"] for p in base.listar(limite=5000) if p["estado"] not in ("pendiente_pago", "cancelado")}
        activas = [f for f in base.listar_fechas(solo_activas=True) if f.get("pedido") in cobrados]
        salida_fechas = []
        por_tipo = {}
        por_vinculo = {}
        for f in activas:
            prox, dias = proxima_ocurrencia(f["dia"], f["mes"], hoy)
            t = f["tipo"]
            por_tipo[t] = por_tipo.get(t, 0) + 1
            v = (f.get("vinculo") or "").strip().lower()
            if v:
                por_vinculo[v] = por_vinculo.get(v, 0) + 1
            salida_fechas.append({
                "id": f["id"],
                "pedido": f["pedido"],
                "nombre": f["nombre"],
                "email": f["email"],
                "whatsapp": f["whatsapp"],
                "marca": f["marca"],
                "para_quien": f["para_quien"],
                "vinculo": f.get("vinculo") or "",
                "tipo": f["tipo"],
                "otra": f.get("otra") or "",
                "dia": f["dia"],
                "mes": f["mes"],
                "creado": f["creado"],
                "proxima": prox.isoformat(),
                "dias_faltan": dias,
                "ultimo_aviso_anio": f.get("ultimo_aviso_anio"),
                "aviso_enviado_este_anio": f.get("ultimo_aviso_anio") == prox.year,
            })
        salida_fechas.sort(key=lambda x: (x["dias_faltan"], x["mes"], x["dia"]))

        anio = hoy.year
        def cuenta_vinculo(palabras):
            c = 0
            for f in activas:
                v = (f.get("vinculo") or "").strip().lower()
                if any(p in v for p in palabras):
                    c += 1
            return c

        def proxima_comercial(calcular):              # la de este año; si ya pasó, la del año que viene
            d = calcular(anio)
            return d if d >= hoy else calcular(anio + 1)
        f_madre = proxima_comercial(lambda y: tercer_domingo(y, 10))
        f_padre = proxima_comercial(lambda y: tercer_domingo(y, 6))
        f_nino = proxima_comercial(lambda y: tercer_domingo(y, 8))
        f_valentin = proxima_comercial(lambda y: date(y, 2, 14))
        f_navidad = proxima_comercial(lambda y: date(y, 12, 25))

        comerciales = [
            {"nombre": "Día de la Madre", "fecha": f_madre.isoformat(), "dia": f_madre.day, "mes": f_madre.month,
             "contactos": cuenta_vinculo(["mamá", "mama", "madre"])},
            {"nombre": "Día del Padre", "fecha": f_padre.isoformat(), "dia": f_padre.day, "mes": f_padre.month,
             "contactos": cuenta_vinculo(["papá", "papa", "padre"])},
            {"nombre": "Día del Niño", "fecha": f_nino.isoformat(), "dia": f_nino.day, "mes": f_nino.month,
             "contactos": len(activas)},
            {"nombre": "San Valentín", "fecha": f_valentin.isoformat(), "dia": f_valentin.day, "mes": f_valentin.month,
             "contactos": cuenta_vinculo(["pareja", "novio", "novia", "esposo", "esposa"])},
            {"nombre": "Navidad", "fecha": f_navidad.isoformat(), "dia": f_navidad.day, "mes": f_navidad.month,
             "contactos": len(activas)},
        ]

        return {
            "fechas": salida_fechas,
            "cantidades": {
                "por_tipo": por_tipo,
                "por_vinculo": por_vinculo,
                "total": len(activas),
            },
            "fechas_comerciales": comerciales,
        }

    def _pagina_baja(marca: str, titulo: str, cuerpo: str) -> str:
        tc = marca == "tc"
        fondo, tinta, boton = ("#F6F7FA", "#16205A", "#E0435C") if tc else ("#FFD23F", "#1A1712", "#D7301F")
        return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(titulo)} · Tu Tiendita IA</title>
<style>
body {{margin:0;padding:40px 20px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:{fondo};color:{tinta};display:flex;justify-content:center}}
main {{max-width:480px;width:100%;background:#fff;border-radius:12px;padding:32px;box-sizing:border-box;box-shadow:0 4px 20px rgba(0,0,0,0.06)}}
h1 {{font-size:24px;margin:0 0 16px;font-weight:800}}
p {{font-size:16px;line-height:1.5;color:#333;margin:0 0 24px}}
button {{background:{boton};color:#fff;font-weight:700;font-size:16px;border:0;border-radius:6px;padding:12px 24px;cursor:pointer;min-height:48px;width:100%}}
button:hover {{opacity:0.9}}
</style></head><body><main>{cuerpo}</main></body></html>"""

    @app.get("/baja/{token}", response_class=HTMLResponse)
    def baja_ver(token: str):
        f = base.obtener_fecha_por_token(token)
        if not f:
            raise HTTPException(404, "No encontramos este enlace de baja o ya no es válido.")
        cuerpo = f"""
        <h1>Dejar de recibir recordatorios</h1>
        <p>Confirmá si querés dejar de recibir avisos de fechas para el regalo de <b>{html.escape(f['para_quien'])}</b>.</p>
        <form method="POST">
          <button type="submit">Dejar de recibir recordatorios</button>
        </form>
        """
        return HTMLResponse(_pagina_baja(f["marca"], "Baja de recordatorios", cuerpo), headers={"Cache-Control": "no-store"})

    @app.post("/baja/{token}", response_class=HTMLResponse)
    def baja_confirmar(token: str):
        f = base.obtener_fecha_por_token(token)
        if not f:
            raise HTTPException(404, "No encontramos este enlace de baja o ya no es válido.")
        base.dar_baja_fecha(token)
        cuerpo = """
        <h1>Listo</h1>
        <p>Listo, no te vamos a escribir más por esta fecha.</p>
        """
        return HTMLResponse(_pagina_baja(f["marca"], "Baja confirmada", cuerpo), headers={"Cache-Control": "no-store"})


    @app.post("/admin/vigilante")
    def admin_vigilante(prueba: bool = False, authorization: str | None = Header(None)):
        """Revisa ya las publicaciones de proveedores (prueba=true: solo lee, no ajusta ni avisa)."""
        _admin(authorization)
        resumen = vigia.revisar(forzar=True, prueba=prueba)
        return {"lecturas": resumen, "precios": {k: p.precio for k, p in catalogo.PRODUCTOS.items() if "cuadro" in k}}

    @app.get("/admin/diagnostico")
    def admin_diagnostico(authorization: str | None = Header(None)):
        """Qué claves cargó el servidor. Nunca muestra valores: solo si están y cuántos caracteres tienen."""
        _admin(authorization)
        def estado(v):
            return f"ok ({len(v)} caracteres)" if v else "FALTA"
        import pathlib as _p
        return {
            "mp_modo": cfg.mp_modo,
            "mp_access_token": estado(cfg.mp_access_token)
                               + (" · formato APP_USR" if cfg.mp_access_token.startswith("APP_USR-") else " · formato raro"),
            "mp_webhook_secret": estado(cfg.mp_webhook_secret),
            "smtp_user": estado(cfg.smtp_user), "smtp_password": estado(cfg.smtp_password),
            "whatsapp_negocio": estado(cfg.whatsapp_negocio), "ntfy_topic": estado(cfg.ntfy_topic),
            "drive_token": "ok" if cfg.drive_token_archivo and _p.Path(cfg.drive_token_archivo).exists() else "FALTA",
            "url_publica": cfg.url_publica, "url_webhook": cfg.url_webhook, "url_revision": cfg.url_revision,
            "caracteres_raros": [n for n, v in (("token", cfg.mp_access_token), ("secreto", cfg.mp_webhook_secret),
                                                ("smtp", cfg.smtp_password)) if any(ord(ch) < 32 for ch in v)],
        }

    @app.get("/admin/pedidos/{pid}")
    def admin_pedido(pid: str, authorization: str | None = Header(None)):
        _admin(authorization)
        p = base.obtener(pid.upper())
        if not p:
            raise HTTPException(404, "No existe")
        return {**p, "resumen": flujo.resumen(p)}

    @app.post("/admin/pedidos/{pid}/reintentar")
    def admin_reintentar(pid: str, authorization: str | None = Header(None)):
        _admin(authorization)
        p = base.obtener(pid.upper())
        if not p or p["estado"] == "pendiente_pago":
            raise HTTPException(409, "El pedido no está pagado")
        flujo.al_pagar(cfg, base, drive(), p["id"])
        return {"ok": True, "error": base.obtener(p["id"])["error"]}

    @app.post("/admin/pedidos/{pid}/transferencia")
    def admin_transferencia(pid: str, authorization: str | None = Header(None)):
        """Viste el comprobante y la plata entró: el pedido pasa a pagado y arranca como cualquier pago
        (carpeta en Drive, mail al cliente, aviso al celular)."""
        _admin(authorization)
        p = base.obtener(pid.upper())
        if not p:
            raise HTTPException(404, "No existe")
        if not base.marcar_pagado_transferencia(p["id"]):
            raise HTTPException(409, f"El pedido está {p['estado']}: solo se aprueba si sigue esperando el pago "
                                     "(si venció, pedile que lo haga de nuevo)")
        flujo.al_pagar(cfg, base, drive(), p["id"])
        return {"ok": True, "estado": base.obtener(p["id"])["estado"], "error": base.obtener(p["id"])["error"]}

    @app.post("/admin/conciliar")
    def admin_conciliar(authorization: str | None = Header(None)):
        _admin(authorization)
        conciliar()
        return {"ok": True}

    async def _guardar_archivos(request, pid, sub):
        form = await request.form(max_files=40, max_part_size=1024 * 1024)
        carpeta = cfg.datos_dir / sub / pid
        carpeta.mkdir(parents=True, exist_ok=True)
        rutas = []
        for f in form.getlist("archivos"):
            if isinstance(f, UploadFile) and f.filename:
                ruta = carpeta / os.path.basename(f.filename)
                with open(ruta, "wb") as out:
                    while bloque := await f.read(1024 * 1024):
                        out.write(bloque)
                rutas.append(ruta)
        if not rutas:
            raise HTTPException(422, "Faltan los archivos")
        return carpeta, rutas, (form.get("mensaje") or "").strip()

    @app.post("/admin/pedidos/{pid}/vista-previa")
    async def admin_vista_previa(pid: str, request: Request, authorization: str | None = Header(None)):
        _admin(authorization)
        p = base.obtener(pid.upper())
        if not p or p["estado"] not in ("pagado", "cambio", "vista_previa"):
            raise HTTPException(409, f"El pedido está en estado {p['estado'] if p else 'inexistente'}")
        carpeta, rutas, mensaje = await _guardar_archivos(request, p["id"], "vistas")
        link = flujo.enviar_vista_previa(cfg, base, drive(), p["id"], rutas, mensaje)
        shutil.rmtree(carpeta, ignore_errors=True)
        return {"ok": True, "link": link}

    @app.post("/admin/pedidos/{pid}/entrega")
    async def admin_entrega(pid: str, request: Request, authorization: str | None = Header(None)):
        _admin(authorization)
        p = base.obtener(pid.upper())
        if not p or p["estado"] not in ("pagado", "aprobado", "entregado"):
            raise HTTPException(409, "El pedido no está pagado ni aprobado")
        carpeta, rutas, mensaje = await _guardar_archivos(request, p["id"], "entregas")
        link = flujo.entregar(cfg, base, drive(), p["id"], rutas, mensaje)
        shutil.rmtree(carpeta, ignore_errors=True)
        return {"ok": True, "link": link}

    @app.patch("/admin/pedidos/{pid}/contacto")
    async def admin_contacto(pid: str, request: Request, authorization: str | None = Header(None)):
        _admin(authorization)
        p = base.obtener(pid.upper())
        if not p:
            raise HTTPException(404, "No existe")
        try:
            datos = await request.json()
        except Exception:
            raise HTTPException(400, "JSON inválido")
        if not isinstance(datos, dict):
            raise HTTPException(400, "JSON inválido")

        cambios = {}
        if "email" in datos:
            email = (str(datos.get("email") or "")).strip()
            if not email:
                raise ErrorCampo("email", "El email es obligatorio.")
            error_mail = correo.problema(email, revisado=True)
            if error_mail:
                raise ErrorCampo("email", error_mail)
            usuario, _, dominio = email.rpartition("@")
            email = f"{usuario}@{dominio.lower()}"
            cambios["email"] = email

        if "whatsapp" in datos:
            wa_raw = str(datos.get("whatsapp") or "").strip()
            whatsapp = avisos.normalizar_whatsapp(wa_raw)
            if not (12 <= len(whatsapp) <= 15):
                raise ErrorCampo("whatsapp", "Revisá el WhatsApp: código de área y número, sin 0 ni 15.")
            cambios["whatsapp"] = whatsapp

        if not cambios:
            raise HTTPException(400, "No se enviaron campos para actualizar")

        base.actualizar(p["id"], **cambios)
        return base.obtener(p["id"])

    @app.post("/admin/pedidos/{pid}/reenviar")
    async def admin_reenviar(pid: str, request: Request, authorization: str | None = Header(None)):
        _admin(authorization)
        p = base.obtener(pid.upper())
        if not p:
            raise HTTPException(404, "No existe")
        try:
            datos = await request.json()
        except Exception:
            raise HTTPException(400, "JSON inválido")
        que = datos.get("que") if isinstance(datos, dict) else None
        if que not in ("vista_previa", "entrega"):
            raise ErrorCampo("que", "El campo 'que' debe ser 'vista_previa' o 'entrega'")

        if que == "vista_previa":
            if not p.get("vista_url"):
                raise HTTPException(409, "El pedido no tiene vista previa para reenviar")
            flujo._mail_vista_previa(cfg, p)
        elif que == "entrega":
            if not p.get("entrega_url"):
                raise HTTPException(409, "El pedido no tiene entrega para reenviar")
            flujo._mail_entrega(cfg, p, p["entrega_url"])

        return {"ok": True}

    @app.post("/admin/pedidos/{pid}/cambio")
    async def admin_cambio(pid: str, request: Request, authorization: str | None = Header(None)):
        _admin(authorization)
        p = base.obtener(pid.upper())
        if not p:
            raise HTTPException(404, "No existe")
        if p["estado"] != "vista_previa":
            raise HTTPException(409, f"El pedido está en estado {p['estado']}")
        try:
            datos = await request.json()
        except Exception:
            raise HTTPException(400, "JSON inválido")
        if not isinstance(datos, dict):
            raise HTTPException(400, "JSON inválido")
        texto = (str(datos.get("texto") or "")).strip()
        if len(texto) < 5:
            raise ErrorCampo("texto", "Contanos qué querés cambiar.")
        sin_costo = datos.get("sin_costo", True)
        if sin_costo:
            base.actualizar(p["id"], cambios_extra=(p.get("cambios_extra") or 0) + 1)
        nuevo_estado = flujo.registrar_respuesta(cfg, base, p["id"], "cambio", texto)
        p_act = base.obtener(p["id"])
        return {"ok": True, "estado": nuevo_estado, "cambios": p_act.get("cambios") or 0,
                "cambios_extra": p_act.get("cambios_extra") or 0}

    @app.post("/admin/pedidos/{pid}/cambios-extra")
    async def admin_cambios_extra(pid: str, request: Request, authorization: str | None = Header(None)):
        _admin(authorization)
        p = base.obtener(pid.upper())
        if not p:
            raise HTTPException(404, "No existe")
        if p["estado"] not in ("vista_previa", "cambio"):
            raise HTTPException(409, f"El pedido está en estado {p['estado']}")
        try:
            datos = await request.json()
        except Exception:
            raise HTTPException(400, "JSON inválido")
        if not isinstance(datos, dict):
            raise HTTPException(400, "JSON inválido")
        cantidad = datos.get("cantidad")
        if not isinstance(cantidad, int) or isinstance(cantidad, bool) or not (1 <= cantidad <= 3):
            raise ErrorCampo("cantidad", "La cantidad debe ser un número entero de 1 a 3.")
        nuevo_extra = (p.get("cambios_extra") or 0) + cantidad
        base.actualizar(p["id"], cambios_extra=nuevo_extra)
        p_act = base.obtener(p["id"])
        quedan = flujo.cambios_max(p_act) - (p_act.get("cambios") or 0)
        return {"ok": True, "cambios_extra": nuevo_extra, "quedan": quedan}

    @app.post("/admin/pedidos/{pid}/seguimiento")
    async def admin_seguimiento(pid: str, request: Request, authorization: str | None = Header(None)):
        _admin(authorization)
        p = base.obtener(pid.upper())
        if not p:
            raise HTTPException(404, "No existe")
        prod = catalogo.PRODUCTOS.get(p["producto"])
        if not prod or not prod.envio:
            raise HTTPException(409, "El pedido no es de un producto con envío (cuadro)")
        if p["estado"] not in ("aprobado", "entregado"):
            raise HTTPException(409, f"El pedido está en estado {p['estado']} (requiere aprobado o entregado)")
        try:
            datos = await request.json()
        except Exception:
            raise HTTPException(422, "JSON inválido")
        if not isinstance(datos, dict):
            raise HTTPException(422, "JSON inválido")

        previa = bool(datos.get("previa"))   # solo arma y devuelve el texto (la centralita lo muestra antes de confirmar)
        if p.get("seguimiento") and not datos.get("reenviar") and not previa:
            raise HTTPException(409, "El pedido ya tiene seguimiento cargado. Usá reenviar=true para actualizarlo.")

        numero = str(datos.get("numero") or "").strip()
        if not (4 <= len(numero) <= 60) or "\n" in numero or "\r" in numero:
            raise HTTPException(422, "El número de seguimiento debe tener entre 4 y 60 caracteres sin saltos de línea.")

        url_raw = datos.get("url")
        url = str(url_raw).strip() if url_raw else None
        if url and (not url.startswith("https://") or len(url) > 300 or any(c.isspace() for c in url)):
            raise HTTPException(422, "El link de seguimiento tiene que empezar con https://, sin espacios (hasta 300 caracteres).")

        empresa_raw = datos.get("empresa")
        empresa = str(empresa_raw).strip() if empresa_raw else None
        if empresa == "":
            empresa = None

        partes_seg = [f"Número de seguimiento: {numero}"]
        if empresa:
            partes_seg[0] += f" ({empresa})"
        if url:
            partes_seg.append(f"seguilo acá: {url}")
        texto_seg = ", ".join(partes_seg) if url else partes_seg[0]
        inicio = f"¡Hola {p['nombre']}! Tu cuadro del pedido {p['id']} ya está en camino. {texto_seg}."
        texto_cliente = f"{inicio} Cualquier duda, respondé este mail."
        texto_wa = f"{inicio} Cualquier duda, escribime por acá."
        if previa:
            return {"ok": True, "previa": True, "texto": texto_cliente, "texto_whatsapp": texto_wa}

        ahora_str = datetime.now(timezone.utc).isoformat(timespec="seconds")
        base.actualizar(p["id"], seguimiento=numero, seguimiento_url=url, cuadro_comprado=ahora_str)

        asunto = f"Tu cuadro del pedido {p['id']} ya está en camino"
        avisos.mandar_mail(cfg, p["email"], asunto, texto_cliente)

        link_wa = avisos.link_whatsapp(p["whatsapp"], texto_wa)
        acciones = [{"action": "view", "label": "Mandar WhatsApp", "url": link_wa}]
        avisos.avisar(cfg, f"📦 Cuadro en camino: {p['id']}", f"{p['nombre']} · Seguimiento: {numero}",
                     acciones=acciones, prioridad=4, tags=("package",))

        return {"ok": True, "texto": texto_cliente, "seguimiento": numero, "cuadro_comprado": ahora_str}


    # ---- página de revisión para el cliente (link con token en el mail) ----
    def _pedido_con_token(pid, t):
        p = base.obtener(pid.upper())
        if not p or not p.get("cliente_token") or not secrets.compare_digest(p["cliente_token"], t or ""):
            raise HTTPException(404, "Link inválido")
        return p

    @app.get("/revisar/{pid}", response_class=HTMLResponse)
    def revisar(pid: str, t: str = ""):
        return _pagina_revision(_pedido_con_token(pid, t), t)

    @app.post("/revisar/{pid}", response_class=HTMLResponse)
    async def revisar_respuesta(pid: str, request: Request):
        form = await request.form()
        t = form.get("t") or ""
        p = _pedido_con_token(pid, t)
        accion = form.get("accion")
        if p["estado"] != "vista_previa":
            return _pagina_revision(p, t)
        if accion == "aprobar":
            flujo.registrar_respuesta(cfg, base, p["id"], "aprobar")
        elif accion == "cambio":
            texto = (form.get("texto") or "").strip()
            if len(texto) < 5:
                return _pagina_revision(p, t, "Contanos qué querés cambiar.")
            if (p.get("cambios") or 0) >= flujo.cambios_max(p):
                return _pagina_revision(p, t, "Ya usaste los cambios incluidos. Escribinos por WhatsApp.")
            flujo.registrar_respuesta(cfg, base, p["id"], "cambio", texto)
        return _pagina_revision(base.obtener(p["id"]), t)

    def _pagina_revision(p, t, error=""):
        tc = p["marca"] == "tc"
        fondo, tinta, acento, boton = (("#F6F7FA", "#16205A", "#1E3C96", "#E0435C") if tc
                                       else ("#FFD23F", "#1A1712", "#1A1712", "#D7301F"))
        e = html.escape
        restantes = flujo.cambios_max(p) - (p.get("cambios") or 0)
        deshabilitado = "disabled" if restantes <= 0 else ""
        if p["estado"] == "vista_previa":
            cuerpo = f"""
<p>{'Escuchá' if tc else 'Mirá'} la vista previa y después elegí:</p>
<a class="ver" href="{e(p.get('vista_url') or '#')}" target="_blank" rel="noopener">{'Escuchar la vista previa' if tc else 'Ver cómo quedó tu foto'} →</a>
<form method="post"><input type="hidden" name="t" value="{e(t)}"><input type="hidden" name="accion" value="aprobar">
<button class="ok" type="submit">Me encanta, aprobar</button></form>
<form method="post" class="cambio"><input type="hidden" name="t" value="{e(t)}"><input type="hidden" name="accion" value="cambio">
<label for="texto">¿Querés cambiar algo? {flujo.quedan_cambios(restantes)}</label>
<textarea id="texto" name="texto" rows="4" maxlength="2000" placeholder="Contanos qué cambiarías"></textarea>
<button type="submit" {deshabilitado}>Pedir el cambio</button></form>"""
        elif p["estado"] == "cambio":
            cuerpo = "<p>Recibimos tu pedido de cambio. En cuanto esté la nueva versión te avisamos por mail y WhatsApp.</p>"
        elif p["estado"] == "aprobado":
            cuerpo = "<p>¡Gracias! Aprobaste la vista previa. Te mandamos la versión final por mail y WhatsApp.</p>"
        elif p["estado"] == "entregado":
            cuerpo = f'<p>Tu pedido ya fue entregado. <a href="{e(p.get("entrega_url") or "#")}">Descargarlo</a>.</p>'
        else:
            cuerpo = "<p>Todavía estamos trabajando en tu pedido. Te avisamos cuando esté la vista previa.</p>"
        aviso = f'<p class="error" role="alert">{e(error)}</p>' if error else ""
        producto = e(catalogo.PRODUCTOS[p["producto"]].nombre)
        return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Pedido {e(p['id'])}</title><style>
body{{margin:0;background:{fondo};color:{tinta};padding:32px 16px;
font:17px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,system-ui,sans-serif}}
button,textarea{{font-family:inherit}}
main{{max-width:560px;margin:0 auto;display:grid;gap:18px}} h1{{margin:0;font-size:28px;color:{acento}}}
a.ver{{display:flex;align-items:center;justify-content:center;min-height:52px;padding:0 16px;font-weight:700;
color:{acento};background:#fff;border:2px solid {acento};border-radius:6px;text-decoration:none}} form{{display:grid;gap:10px}}
button{{font-weight:700;font-size:18px;min-height:52px;padding:0 20px;border:0;border-radius:6px;background:{acento};color:#fff;cursor:pointer}}
button.ok{{background:{boton}}} button[disabled]{{opacity:.5}}
textarea{{font-size:16px;padding:10px;border:2px solid {tinta};border-radius:6px}}
.cambio{{border-top:2px solid {tinta};padding-top:18px}} .error{{color:{boton};font-weight:700}}
button:focus-visible,a:focus-visible,textarea:focus-visible{{outline:3px solid {boton};outline-offset:2px}}
</style></head><body><main><h1>Pedido {e(p['id'])}</h1><p>Hola {e(p['nombre'])}: {producto}.</p>
{aviso}{cuerpo}</main></body></html>"""

    return app


app = crear_app() if os.environ.get("TIENDA_AUTOARRANQUE", "1") == "1" else None
