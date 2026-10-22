"""Vigilante de proveedores (corre en el servidor, cada 30 minutos, dentro del ciclo de la tienda).

Lee cada publicación de proveedores.json desde el link social de afiliado (meli.la/…): la página pública de tu perfil
trae la "tarjeta destacada" del producto con número, título, precio, vendedor y el texto de envío tal cual lo ve
cualquier comprador. (La API oficial de ML no deja leer publicaciones de otros vendedores: 403 desde 2025.)

  - Precio: calcula el precio de venta de cada producto con su costo (si tiene varias publicaciones, como el enmarcado
    madera/negro, usa la más cara) y, si no coincide con el de la tienda, lo ajusta solo (datos/precios.json).
    Si el precio nuevo difiere en más de un 40% del actual, no ajusta y avisa (puede ser un error o una oferta).
  - Envío: avisa si no dice "Llega gratis mañana". En las marcadas con gratis_con_tu_cuenta (gratis por Meli+, que la
    página pública no muestra) solo controla que llegue mañana. Si la tarjeta viene sin el dato de envío (ML a veces la
    manda incompleta: 19/10 07:56), no es un cambio: avisa recién si pasa en LECTURAS_SIN_ENVIO revisiones seguidas.
  - Avisa también si una publicación no se puede leer, cambia de vendedor o el link pasa a mostrar otra.
Un mismo aviso se repite cada 6 horas como mucho. Avisos por ntfy y, si están CALLMEBOT_APIKEY y WHATSAPP_AVISOS en el
entorno, también por WhatsApp.
"""
from datetime import datetime, timezone
import functools
import json
import math
import os
import pathlib
import re
import threading
import time

import httpx

CONFIG = pathlib.Path(__file__).with_name("proveedores.json")
CADA = 30 * 60
REPETIR_AVISO = 6 * 3600
TOPE_CAMBIO = 0.40
LECTURAS_SIN_ENVIO = 3          # revisiones seguidas sin dato de envío antes de avisar (con CADA = 30 min, una hora)


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

# La comisión de Mercado Pago ya no es un número fijo (era NETO_MP = 0,92, D-15): es la real de los cobros, por la API
# de MP (pagos.py, D-49). Sin ese dato no se cambian precios.
NAVEGADOR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/130.0 Safari/537.36", "Accept-Language": "es-AR,es;q=0.9"}


# ---------------- configuración ----------------
def config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def publicaciones() -> list:
    return config()["publicaciones"]


def link_compra(producto: str, marco: str | None = None) -> str:
    """Link de la publicación para comprar el cuadro (en el enmarcado, la del color de marco elegido)."""
    candidatas = [x for x in publicaciones() if x["producto"] == producto]
    elegida = next((x for x in candidatas if marco and x.get("marco") == marco), candidatas[0] if candidatas else None)
    return elegida["url"] if elegida else ""


def pesos(n) -> str:
    return f"${n:,}".replace(",", ".") if isinstance(n, int) else "$?"


def precio_de_venta(regla: dict, costo: int, tasa_mp: float) -> int:
    """Precio que deja la ganancia neta de la regla después de la comisión real de MP (tasa_mp, por ejemplo 0,043),
    redondeado hacia arriba a $…999."""
    queda = 1 - tasa_mp
    neto = regla["ganancia_neta"] if "ganancia_neta" in regla else regla["precio_base"] * queda - regla["costo_base"]
    bruto = (costo + neto) / queda
    return math.ceil((bruto + 1) / 1000) * 1000 - 1



# ---------------- modo y historial de precios ----------------
def leer_precios_modo(ruta: pathlib.Path) -> dict[str, dict]:
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def guardar_precio_modo(ruta: pathlib.Path, producto: str, modo: str, ganancia_neta: int | None = None) -> dict:
    modos = leer_precios_modo(ruta)
    entrada = {
        "modo": modo,
        "ganancia_neta": ganancia_neta,
        "fecha": ahora_iso(),
    }
    modos[producto] = entrada
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(modos, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(ruta)
    return entrada


def registrar_historial_precio(ruta: pathlib.Path, producto: str, antes: int, despues: int, quien: str):
    if antes == despues:
        return
    registro = {
        "fecha": ahora_iso(),
        "producto": producto,
        "antes": antes,
        "despues": despues,
        "quien": quien,
    }
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def leer_historial_precios(ruta: pathlib.Path, limite: int = 50) -> list[dict]:
    if not ruta.is_file():
        return []
    lineas = ruta.read_text(encoding="utf-8").strip().splitlines()
    salida = []
    for l in reversed(lineas):
        l = l.strip()
        if not l:
            continue
        try:
            salida.append(json.loads(l))
            if len(salida) >= limite:
                break
        except json.JSONDecodeError:
            continue
    return salida


# ---------------- lectura del link social ----------------
def _tarjetas(html: str) -> list:
    dec = json.JSONDecoder()
    salida = []
    for m in re.finditer(r'\{"unique_id":', html):
        try:
            obj, _ = dec.raw_decode(html, m.start())
        except json.JSONDecodeError:
            continue
        salida.append(obj)
    return salida


def _valor(comp: dict, tipo: str, *ruta):
    x = comp.get(tipo) or {}
    for clave in ruta:
        x = x.get(clave) if isinstance(x, dict) else None
    return x if isinstance(x, (str, int, float)) else ""


def leer(url: str) -> dict:
    r = httpx.get(url, headers=NAVEGADOR, follow_redirects=True, timeout=30)
    if r.status_code != 200 or re.search(r"account-verification|captcha", str(r.url)):
        return {"error": f"ML no mostró la página del link ({r.status_code})."}
    destacadas = [c for c in _tarjetas(r.text) if "card-featured" in (c.get("metadata") or {}).get("url_fragments", "")]
    if not destacadas:
        return {"error": "La página del link no trae la tarjeta del producto (¿cambió ML o se pausó la publicación?)."}
    c = destacadas[0]
    comp = {x.get("type"): x for x in c.get("components", [])}
    precio = _valor(comp, "price", "price", "current_price", "value")
    envio = _valor(comp, "shipping", "shipping", "text")
    promesa = _valor(comp, "shipping", "shipping", "promise_type")
    meta = c.get("metadata") or {}
    vendedor = _valor(comp, "seller", "seller", "text") or _valor(comp, "brand", "brand", "text")
    return {"error": "", "item_id": meta.get("id", ""), "titulo": _valor(comp, "title", "title", "text"),
            "permalink": "https://" + meta["url"] if meta.get("url") else url,
            "precio": round(precio) if precio else None,
            "vendedor": re.sub(r"^Por\s+|\{[^}]*\}", "", vendedor).strip(),
            "activa": bool(precio), "envio": envio or "sin datos de envío", "sin_envio": not envio,
            "llega_manana": promesa in ("next_day", "same_day") or bool(re.search(r"\b(hoy|mañana)\b", envio, re.I)),
            "gratis": "gratis" in envio.lower()}


# ---------------- avisos ----------------
def whatsapp(titulo: str, mensaje: str, url: str | None = None):
    clave, numero = os.environ.get("CALLMEBOT_APIKEY"), os.environ.get("WHATSAPP_AVISOS")
    if clave and numero:
        try:
            httpx.get("https://api.callmebot.com/whatsapp.php", timeout=20, params={
                "phone": numero, "apikey": clave, "text": f"*{titulo}*\n{mensaje}" + (f"\n{url}" if url else "")})
        except Exception:
            pass


def _con_candado(metodo):
    """El estado (proveedores-estado.json) se lee y se guarda entero. Una revisión tarda varios segundos (lee las
    publicaciones): si en ese rato se carga un precio a mano o se aprueba un cambio, la que guarda última pisaría a la
    otra. Con el candado, una espera a la otra."""
    @functools.wraps(metodo)
    def envuelto(self, *a, **k):
        with self._candado:
            return metodo(self, *a, **k)
    return envuelto


class Vigilante:
    """avisar(titulo, mensaje, url, prioridad), vigentes() -> {producto: precio}, ajustar(producto, precio)."""

    def __init__(self, estado: pathlib.Path, avisar, vigentes, ajustar, log=print, lector=None, comision=None):
        self.estado_ruta, self.avisar, self.vigentes, self.ajustar, self.log = estado, avisar, vigentes, ajustar, log
        self.lector = lector
        self.comision = comision or (lambda: None)   # () -> {"tasa", "porcentaje", "pagos", ...} o None (pagos.py)
        self.ruta_modo = self.estado_ruta.with_name("precios-modo.json")
        self.ruta_historial = self.estado_ruta.with_name("precios-historial.jsonl")
        self._candado = threading.RLock()


    def _comision(self, est) -> dict | None:
        """La comisión real de MP leída ahora; si MP no responde, la última real que se leyó (queda con su fecha)."""
        try:
            actual = self.comision()
        except Exception as e:
            self.log(f"No pude leer la comisión real de MP: {e}")
            actual = None
        if actual:
            est["comision_mp"] = actual
            self._resuelto(est, "comision_mp")
        return est.get("comision_mp")

    # estado: cuándo se revisó y qué avisos están activos
    def _estado(self) -> dict:
        try:
            return json.loads(self.estado_ruta.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _guardar(self, e: dict):
        tmp = self.estado_ruta.with_suffix(".tmp")
        tmp.write_text(json.dumps(e, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.estado_ruta)

    def _una_vez(self, est, clave, titulo, mensaje, url=None, prioridad=4):
        avisos = est.setdefault("avisos", {})
        if time.time() - avisos.get(clave, 0) >= REPETIR_AVISO:
            self.avisar(titulo, mensaje, url, prioridad)
            avisos[clave] = time.time()

    @staticmethod
    def _resuelto(est, clave):
        est.setdefault("avisos", {}).pop(clave, None)

    @_con_candado
    def revisar(self, forzar=False, prueba=False) -> list:
        """Devuelve lo leído de cada publicación. prueba=True: solo lee (no ajusta ni avisa ni guarda)."""
        est = self._estado()
        if not forzar and time.time() - est.get("ultima", 0) < CADA:
            return []
        if not prueba:
            est["ultima"] = time.time()
            self._guardar(est)
        cfg = config()
        vigentes = self.vigentes()
        lecturas, resumen = {}, []
        for prov in cfg["publicaciones"]:
            r = self._leer_publicacion(prov, est, prueba)
            lecturas.setdefault(prov["producto"], []).append((prov, r))
            resumen.append({"nombre": prov["nombre"], **(r or {"error": "ver avisos"})})
        if not prueba:
            comision = self._comision(est)
            if comision:
                for prod, lista in lecturas.items():
                    self._ajustar_producto(prod, lista, cfg["productos"].get(prod), vigentes.get(prod), est,
                                           comision["tasa"])
            else:
                self._una_vez(est, "comision_mp", "⚠ Precios de cuadros sin ajustar",
                              "Todavía no tengo la comisión real de Mercado Pago (no hay cobros aprobados leídos por la "
                              "API). No cambié ningún precio: no uso porcentajes inventados.", None, 4)
            est["revisado"] = ahora_iso()          # con zona horaria: el servidor está en Europa, la PC en Argentina
            self._guardar(est)
        return resumen

    def _leer_publicacion(self, prov, est, prueba):
        nombre, url = prov["nombre"], prov["url"]
        try:
            r = (self.lector or leer)(url)
        except Exception as e:
            r = {"error": f"No pude abrir el link: {e}"}
        if r.get("error"):
            self.log(f"{nombre}: {r['error']}")
            if not prueba:
                self._una_vez(est, f"{nombre}:lectura", f"⚠ No pude revisar {nombre}", r["error"], url)
                est.setdefault("lecturas", {})[nombre] = {
                    "fecha": ahora_iso(), "precio": None, "envio": "", "vendedor": "",
                    "item_id": prov.get("item_id", ""), "error": r["error"]
                }
            return None if not prueba else r
        self.log(f"{nombre}: {r['item_id']} · {r['vendedor'] or '?'} · costo {pesos(r['precio'])} · «{r['envio']}»")
        if prueba:
            return r
        problemas = []
        if prov.get("item_id") and r["item_id"] != prov["item_id"]:
            problemas.append(f"el link ahora muestra otra publicación ({r['item_id']} «{r['titulo']}»)")
        if not r["activa"]:
            problemas.append("la publicación no tiene precio (¿pausada?)")
        esperado = prov.get("vendedor") or ""
        if esperado and r["vendedor"] and esperado.lower() not in r["vendedor"].lower():
            problemas.append(f"cambió el vendedor: ahora es {r['vendedor']} (antes {esperado})")
        if problemas:
            err_msg = "; ".join(problemas).capitalize() + ". No toqué el precio."
            self._una_vez(est, f"{nombre}:lectura", f"⚠ Revisá la publicación de {nombre}",
                          err_msg, r["permalink"] or url, 5)
            est.setdefault("lecturas", {})[nombre] = {
                "fecha": ahora_iso(), "precio": r.get("precio"), "envio": r.get("envio") or "",
                "vendedor": r.get("vendedor") or "", "item_id": r.get("item_id") or "", "error": err_msg
            }
            return None
        self._resuelto(est, f"{nombre}:lectura")

        est.setdefault("lecturas", {})[nombre] = {
            "fecha": ahora_iso(), "precio": r["precio"], "envio": r["envio"],
            "vendedor": r["vendedor"], "item_id": r["item_id"], "error": ""
        }

        a_mano = est.get("a_mano", {}).get(nombre)
        if a_mano:
            leido_entonces = a_mano.get("leido_entonces")
            if leido_entonces is not None and r["precio"] != leido_entonces:
                est["a_mano"].pop(nombre, None)
                self.avisar(f"⚠ {nombre}: precio a mano descartado",
                            f"Cambió el precio de {nombre}: dejé de usar el que cargaste a mano.", prov["url"])

        est.setdefault("costos", {})[nombre] = r["precio"]
        hist = est.setdefault("historial", {}).setdefault(nombre, [])
        if not hist or hist[-1]["precio"] != r["precio"]:
            hist.append({"fecha": ahora_iso(), "precio": r["precio"], "fuente": "vigilante"})
            if len(hist) > 200:
                del hist[:-200]

        faltas = est.setdefault("sin_envio", {})
        if r.get("sin_envio"):
            faltas[nombre] = faltas.get(nombre, 0) + 1
            self.log(f"{nombre}: la tarjeta vino sin dato de envío ({faltas[nombre]} de {LECTURAS_SIN_ENVIO} seguidas)")
            if faltas[nombre] >= LECTURAS_SIN_ENVIO:
                self._una_vez(est, f"{nombre}:envio", f"🚚 {nombre}: ML no muestra el envío",
                              f"En las últimas {faltas[nombre]} revisiones la página del proveedor vino sin el dato de "
                              "envío. Puede ser una falla de ML o un cambio en la publicación: revisala antes de vender "
                              "ese cuadro.", r["permalink"] or url, 4)
        elif r["llega_manana"] and (r["gratis"] or prov.get("gratis_con_tu_cuenta")):
            faltas.pop(nombre, None)
            self._resuelto(est, f"{nombre}:envio")
        else:
            faltas.pop(nombre, None)
            self._una_vez(est, f"{nombre}:envio", f"🚚 {nombre}: no dice \"Llega gratis mañana\"",
                          f"Ahora dice: «{r['envio']}». Revisá antes de vender ese cuadro.", r["permalink"] or url, 5)
        return r

    def _ajustar_producto(self, prod, lista, regla, vigente, est, tasa_mp):
        """Precio del producto según la publicación más cara; si alguna no se pudo leer, no se toca."""
        if not regla or any(r is None for _, r in lista):
            return

        def _costo_pub(par):
            prov_item, r_item = par
            am = est.get("a_mano", {}).get(prov_item["nombre"])
            if am and am.get("precio"):
                return am["precio"]
            return r_item["precio"] if (r_item and r_item.get("precio")) else 0

        prov, r = max(lista, key=_costo_pub)
        costo = _costo_pub((prov, r))
        url = (r.get("permalink") if isinstance(r, dict) else None) or prov["url"]

        # Modo de precio (Tarea 17): fijo o auto
        modo_info = leer_precios_modo(self.ruta_modo).get(prod, {})
        modo = modo_info.get("modo", "auto")
        if modo == "fijo":
            queda = 1 - tasa_mp
            lo_que_queda = vigente * queda - costo if vigente else 0
            ganancia_regla = regla["ganancia_neta"] if "ganancia_neta" in regla else regla["precio_base"] * queda - regla["costo_base"]
            if round(lo_que_queda) < round(ganancia_regla):
                avisos_fijo = est.setdefault("avisos_fijo", {})
                if avisos_fijo.get(prod) != costo:
                    avisos_fijo[prod] = costo
                    self.avisar(
                        f"⚠ Ganancia baja en {prod}",
                        f"Con el costo nuevo ({pesos(costo)}), el precio fijo de {pesos(vigente)} te deja {pesos(round(lo_que_queda))} por venta (la regla pide {pesos(round(ganancia_regla))}).",
                        url,
                        4,
                    )
            else:
                est.setdefault("avisos_fijo", {}).pop(prod, None)
            return

        if modo_info.get("ganancia_neta") is not None:
            regla = {**regla, "ganancia_neta": modo_info["ganancia_neta"]}

        nuevo = precio_de_venta(regla, costo, tasa_mp)
        nombre = prov["nombre"] if len(lista) == 1 else f"{prod} (la más cara: {prov['nombre']})"
        if vigente == nuevo:
            est.setdefault("pendientes", {}).pop(prod, None)
            self._resuelto(est, f"{prod}:tope")
            return
        if vigente and abs(nuevo - vigente) / vigente > TOPE_CAMBIO:
            if est.get("rechazados", {}).get(prod) == costo:
                return
            est.setdefault("pendientes", {})[prod] = {
                "vigente": vigente,
                "nuevo": nuevo,
                "costo": costo,
                "publicacion": prov["nombre"],
                "fecha": ahora_iso(),
            }
            self._una_vez(est, f"{prod}:tope", f"⚠ Precio raro en {nombre}",
                          f"El costo es {pesos(costo)} y el precio de venta tendría que pasar de {pesos(vigente)} a "
                          f"{pesos(nuevo)} (más de 40%). No lo cambié: revisalo a mano.", url, 5)
            return

        est.setdefault("pendientes", {}).pop(prod, None)
        est.setdefault("rechazados", {}).pop(prod, None)
        antes = vigente
        try:
            self.ajustar(prod, nuevo)
        except Exception as e:
            self._una_vez(est, f"{prod}:ajuste", f"⚠ No pude ajustar el precio de {nombre}",
                          f"Corresponde {pesos(nuevo)} (costo {pesos(costo)}). Error: {e}", url, 5)
            return
        registrar_historial_precio(self.ruta_historial, prod, antes, nuevo, "vigilante")
        self.log(f"{nombre}: costo {pesos(costo)} → precio de venta {pesos(vigente)} → {pesos(nuevo)}")
        self.avisar(f"💲 Precio ajustado: {nombre}",
                    f"El proveedor cobra {pesos(costo)}. Precio de venta: {pesos(vigente)} → {pesos(nuevo)} "
                    f"(misma ganancia neta, con la comisión real de MP: {f'{tasa_mp * 100:.2f}'.replace('.', ',')} %). "
                    "Ya se ve en la web.", url, 4)
        self._resuelto(est, f"{prod}:ajuste")
        self._resuelto(est, f"{prod}:tope")


    def _ajustar_un_producto(self, prod: str, est: dict, cfg: dict):
        regla = cfg["productos"].get(prod)
        if not regla:
            return
        comision = self._comision(est)
        if not comision:
            return
        vigentes = self.vigentes()
        pubs = [p for p in cfg["publicaciones"] if p["producto"] == prod]
        lista = []
        for p in pubs:
            costo = est.get("a_mano", {}).get(p["nombre"], {}).get("precio") or est.get("costos", {}).get(p["nombre"])
            if costo is not None:
                r = {"precio": costo, "permalink": p.get("url")}
            else:
                r = None
            lista.append((p, r))
        if all(r is not None for _, r in lista):
            self._ajustar_producto(prod, lista, regla, vigentes.get(prod), est, comision["tasa"])

    @_con_candado
    def fijar_precio_a_mano(self, nombre: str, precio: int) -> dict:
        if not isinstance(precio, int) or not (1 <= precio <= 10_000_000):
            raise ValueError("El precio debe ser un entero entre 1 y 10.000.000")
        cfg = config()
        prov = next((p for p in cfg["publicaciones"] if p["nombre"] == nombre), None)
        if not prov:
            raise KeyError(f"No existe la publicación {nombre}")
        est = self._estado()
        ahora = ahora_iso()
        leido_entonces = est.get("costos", {}).get(nombre)
        if leido_entonces is None and est.get("lecturas", {}).get(nombre):
            leido_entonces = est["lecturas"][nombre].get("precio")
        est.setdefault("a_mano", {})[nombre] = {
            "precio": precio,
            "fecha": ahora,
            "leido_entonces": leido_entonces,
        }
        hist = est.setdefault("historial", {}).setdefault(nombre, [])
        if not hist or hist[-1]["precio"] != precio:
            hist.append({"fecha": ahora, "precio": precio, "fuente": "a mano"})
            if len(hist) > 200:
                del hist[:-200]
        self._ajustar_un_producto(prov["producto"], est, cfg)
        self._guardar(est)
        return est["a_mano"][nombre]

    @_con_candado
    def quitar_precio_a_mano(self, nombre: str) -> bool:
        cfg = config()
        prov = next((p for p in cfg["publicaciones"] if p["nombre"] == nombre), None)
        if not prov:
            raise KeyError(f"No existe la publicación {nombre}")
        est = self._estado()
        if nombre in est.get("a_mano", {}):
            est["a_mano"].pop(nombre)
            costo_vig = est.get("costos", {}).get(nombre)
            if costo_vig is not None:
                hist = est.setdefault("historial", {}).setdefault(nombre, [])
                if not hist or hist[-1]["precio"] != costo_vig:
                    hist.append({"fecha": ahora_iso(), "precio": costo_vig, "fuente": "vigilante"})
                    if len(hist) > 200:
                        del hist[:-200]
            self._ajustar_un_producto(prov["producto"], est, cfg)
            self._guardar(est)
            return True
        return False

    @_con_candado
    def aprobar_pendiente(self, producto: str) -> dict | None:
        est = self._estado()
        pend = est.get("pendientes", {}).pop(producto, None)
        if not pend:
            return None
        antes = self.vigentes().get(producto)
        self.ajustar(producto, pend["nuevo"])
        registrar_historial_precio(self.ruta_historial, producto, antes, pend["nuevo"], "aprobado")
        est.setdefault("rechazados", {}).pop(producto, None)
        self._resuelto(est, f"{producto}:tope")
        self._guardar(est)
        return pend

    @_con_candado
    def rechazar_pendiente(self, producto: str) -> dict | None:
        est = self._estado()
        pend = est.get("pendientes", {}).pop(producto, None)
        if not pend:
            return None
        est.setdefault("rechazados", {})[producto] = pend["costo"]
        self._resuelto(est, f"{producto}:tope")
        self._guardar(est)
        return pend

    def datos_admin(self) -> dict:
        cfg = config()
        est = self._estado()
        comision = est.get("comision_mp")
        vigentes = self.vigentes()
        pubs_out = []
        for p in cfg["publicaciones"]:
            nom = p["nombre"]
            pubs_out.append({
                "nombre": nom,
                "producto": p["producto"],
                "marco": p.get("marco"),
                "url": p["url"],
                "item_id": p.get("item_id", ""),
                "vendedor": p.get("vendedor", ""),
                "ultima_lectura": est.get("lecturas", {}).get(nom),
                "a_mano": est.get("a_mano", {}).get(nom),
                "historial": est.get("historial", {}).get(nom, []),
            })
        prods_out = {}
        for prod, regla in cfg["productos"].items():
            prods_out[prod] = {
                "precio_vigente": vigentes.get(prod),
                "pendiente": est.get("pendientes", {}).get(prod),
                "regla": regla,
            }
        return {
            "publicaciones": pubs_out,
            "productos": prods_out,
            "comision_mp": comision,
            "ultima_revision": est.get("revisado") or (
                datetime.fromtimestamp(est["ultima"], tz=timezone.utc).isoformat(timespec="seconds")
                if est.get("ultima") else None
            ),
        }

    @_con_candado
    def recalcular_producto(self, prod: str) -> int:
        cfg = config()
        regla = cfg["productos"].get(prod)
        if not regla:
            raise KeyError(f"No existe regla para {prod}")
        est = self._estado()
        comision = self._comision(est)
        if not comision:
            raise ValueError("No hay comisión de Mercado Pago disponible")
        pubs = [p for p in cfg["publicaciones"] if p["producto"] == prod]
        if not pubs:
            raise KeyError(f"No hay publicaciones para {prod}")
        lista = []
        for p in pubs:
            costo = est.get("a_mano", {}).get(p["nombre"], {}).get("precio") or est.get("costos", {}).get(p["nombre"])
            if costo is None and est.get("lecturas", {}).get(p["nombre"]):
                costo = est["lecturas"][p["nombre"]].get("precio")
            lista.append((p, {"precio": costo, "permalink": p.get("url")} if costo is not None else None))
        if any(r is None for _, r in lista):
            raise ValueError(f"Falta el costo de alguna publicación para {prod}")

        def _costo_pub(par):
            prov_item, r_item = par
            am = est.get("a_mano", {}).get(prov_item["nombre"])
            if am and am.get("precio"):
                return am["precio"]
            return r_item["precio"] if (r_item and r_item.get("precio")) else 0

        prov, r = max(lista, key=_costo_pub)
        costo = _costo_pub((prov, r))
        modo_info = leer_precios_modo(self.ruta_modo).get(prod, {})
        if modo_info.get("ganancia_neta") is not None:
            regla = {**regla, "ganancia_neta": modo_info["ganancia_neta"]}
        nuevo = precio_de_venta(regla, costo, comision["tasa"])
        antes = self.vigentes().get(prod)
        self.ajustar(prod, nuevo)
        est.setdefault("pendientes", {}).pop(prod, None)
        self._resuelto(est, f"{prod}:tope")
        self._guardar(est)
        registrar_historial_precio(self.ruta_historial, prod, antes, nuevo, "a mano")
        return nuevo

    @_con_candado
    def fijar_modo(self, prod: str, modo: str, ganancia_neta: int | None = None) -> dict:
        return guardar_precio_modo(self.ruta_modo, prod, modo, ganancia_neta)

    def modo(self, prod: str) -> dict:
        return leer_precios_modo(self.ruta_modo).get(prod, {})

    def historial_precios(self, limite: int = 50) -> list[dict]:
        return leer_historial_precios(self.ruta_historial, limite)


