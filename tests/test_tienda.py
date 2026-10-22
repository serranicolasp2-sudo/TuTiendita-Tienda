"""Pruebas del backend con Mercado Pago, Drive, mail y ntfy simulados (no salen a internet)."""
import hashlib
import hmac
import json
import os
import pathlib
import threading
import urllib.parse
from datetime import date, datetime, timedelta, timezone

os.environ["TIENDA_AUTOARRANQUE"] = "0"

import pytest
from fastapi.testclient import TestClient

from app import avisos, catalogo, correo, flujo, mp, vigilante
from app.config import Config
from app.main import crear_app, revisar_recordatorios_fechas

JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 200
SECRETO = "secreto-de-prueba"


class DriveFalso:
    def __init__(self):
        self.carpetas, self.subidos, self.compartidos = [], [], []

    def carpeta(self, nombre, padre=None):
        cid = f"c{len(self.carpetas)}"
        self.carpetas.append((cid, nombre, padre))
        return {"id": cid, "webViewLink": f"https://drive/{cid}"}

    def buscar_carpeta(self, nombre, padre):
        for cid, n, p in self.carpetas:
            if n == nombre and p == padre:
                return {"id": cid, "webViewLink": f"https://drive/{cid}"}

    def subir(self, ruta, padre, nombre=None):
        self.subidos.append((pathlib.Path(ruta).name, padre))
        return {"id": "a", "webViewLink": "x"}

    def compartir_con_link(self, cid):
        self.compartidos.append(cid)

    def papelera(self, cid):
        self.en_papelera = getattr(self, "en_papelera", []) + [cid]


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    cfg = Config(mp_modo="prueba", mp_access_token="TEST", mp_webhook_secret=SECRETO, smtp_user="t@gmail.com",
                 smtp_password="x", whatsapp_negocio="5491100000000", ntfy_topic="t", drive_token_archivo="",
                 datos_dir=tmp_path, url_publica="https://ej.com", ruta_api="/tutienditaia/api",
                 url_web_tc="https://ej.com/tutienditaia/tucancion",
                 url_web_rf="https://ej.com/tutienditaia/restauraciondefotos", admin_token="adm", aviso_email="d@gmail.com")
    mails, notis, prefs, pagos = [], [], [], {}
    monkeypatch.setattr(avisos, "mandar_mail", lambda cfg, para, asunto, texto, html=None, responder_a=None: mails.append((para, asunto, texto)))
    monkeypatch.setattr(avisos, "avisar", lambda cfg, titulo, mensaje, acciones=None, prioridad=4, tags=(): notis.append((titulo, acciones)))

    def crear_pref(cfg_, pedido, prod):
        prefs.append(pedido)
        return {"id": "pref-1", "init_point": f"https://mp/checkout/{pedido['id']}"}
    monkeypatch.setattr(mp, "crear_preferencia", crear_pref)
    monkeypatch.setattr(mp, "obtener_pago", lambda cfg_, pid: pagos[pid])
    monkeypatch.setattr(mp, "pagos_de_pedido", lambda cfg_, ref: [p for p in pagos.values() if p["external_reference"] == ref])
    monkeypatch.setattr(correo, "recibe_correo", lambda dominio: dominio != "gmail.col")   # sin consultar el DNS real
    drive = DriveFalso()
    app = crear_app(cfg, drive_factory=lambda: drive, conciliar_cada=None)
    return TestClient(app), app, dict(mails=mails, notis=notis, prefs=prefs, pagos=pagos, drive=drive)


def firmar(data_id, request_id="req-1", ts="1700000000"):
    man = f"id:{data_id};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(SECRETO.encode(), man.encode(), hashlib.sha256).hexdigest()
    return {"x-signature": f"ts={ts},v1={v1}", "x-request-id": request_id}


BASE_FOTO = {"producto": "rf-pack-5", "nombre": "Ana Pérez", "email": "ana@mail.com", "whatsapp": "11 15 2345 6789",
             "acepto": "si", "comentarios": "La de la izquierda es mi abuela", "color": "Color"}

BASE_CANCION = {"producto": "tc-cancion", "nombre": "Juan", "email": "juan@mail.com", "whatsapp": "+54 9 351 555 1234",
                "acepto": "si", "para_quien": "Marta", "vinculo": "mamá", "ocasion": "Día de la Madre",
                "voz": "Femenina", "duracion": "Normal (unos 3 minutos)",
                "historia": "Mi vieja cocina los mejores ñoquis del 29 y siempre canta tangos mientras plancha.",
                "inspiracion": "https://youtu.be/abc"}


def test_catalogo_precios_del_servidor(entorno):
    c, _, _ = entorno
    r = c.get("/catalogo?marca=rf").json()
    precios = {p["id"]: p["precio"] for p in r["productos"]}
    assert precios["rf-foto-1"] in (500, 4999) and precios["rf-pack-20"] == 39999
    assert all(p["marca"] == "rf" for p in r["productos"])


def test_pedido_de_fotos_y_pago_completo(entorno):
    c, app, f = entorno
    archivos = [("fotos", ("abuela.jpg", JPG, "image/jpeg")), ("fotos", ("boda.JPEG", JPG, "image/jpeg"))]
    r = c.post("/pedidos", data=BASE_FOTO, files=archivos)
    assert r.status_code == 201, r.text
    pid = r.json()["pedido"]
    assert pid == "RF-0001" and r.json()["init_point"].endswith(pid)
    pedido = app.state.base.obtener(pid)
    assert pedido["whatsapp"] == "5491123456789" and pedido["precio"] == 14999 and len(pedido["archivos"]) == 2

    f["pagos"]["999"] = {"id": 999, "status": "approved", "external_reference": pid, "currency_id": "ARS",
                         "transaction_amount": 14999}
    r = c.post("/mp/webhook?data.id=999&type=payment", json={"type": "payment", "data": {"id": "999"}}, headers=firmar("999"))
    assert r.status_code == 200
    p = app.state.base.obtener(pid)
    assert p["estado"] == "pagado" and p["drive_url"] and not p["error"]
    assert [n for n, _ in f["drive"].subidos].count("pedido.txt") == 1
    assert {"foto-01.jpg", "foto-02.jpg"} <= {n for n, _ in f["drive"].subidos}
    assert any(m[0] == "ana@mail.com" for m in f["mails"]) and any(m[0] == "d@gmail.com" for m in f["mails"])
    assert f["notis"][0][0] == "Pedido pagado RF-0001"
    assert c.get(f"/pedidos/{pid}/estado").json()["estado"] == "pagado"

    # el mismo aviso repetido no duplica nada
    c.post("/mp/webhook?data.id=999&type=payment", json={}, headers=firmar("999"))
    assert len([m for m in f["mails"] if m[0] == "ana@mail.com"]) == 1


def test_webhook_con_firma_falsa_se_rechaza(entorno):
    c, _, _ = entorno
    r = c.post("/mp/webhook?data.id=1&type=payment", json={}, headers={"x-signature": "ts=1,v1=abc", "x-request-id": "r"})
    assert r.status_code == 401


def test_pago_por_menos_plata_no_marca_pagado(entorno):
    c, app, f = entorno
    pid = c.post("/pedidos", data=BASE_CANCION | {"estilos": ["Tango", "Balada"]}).json()["pedido"]
    f["pagos"]["5"] = {"id": 5, "status": "approved", "external_reference": pid, "currency_id": "ARS",
                       "transaction_amount": 100}
    c.post("/mp/webhook?data.id=5&type=payment", json={}, headers=firmar("5"))
    assert app.state.base.obtener(pid)["estado"] == "pendiente_pago"


def test_cancion_valida_campos(entorno):
    c, app, f = entorno
    sin_estilo = c.post("/pedidos", data=BASE_CANCION)
    assert sin_estilo.status_code == 422 and sin_estilo.json()["campo"] == "estilos"
    corta = c.post("/pedidos", data=BASE_CANCION | {"estilos": "Tango", "historia": "corta"})
    assert corta.json()["campo"] == "historia"
    ok = c.post("/pedidos", data=BASE_CANCION | {"estilos": ["Tango", "Inventado"]})
    assert ok.status_code == 201
    datos = app.state.base.obtener(ok.json()["pedido"])["datos"]
    assert datos["estilos"] == ["Tango"] and datos["voz"] == "Femenina"
    assert ok.json()["pedido"] == "TC-0001"


def test_fotos_validaciones(entorno):
    c, _, _ = entorno
    assert c.post("/pedidos", data=BASE_FOTO).json()["campo"] == "fotos"
    seis = [("fotos", (f"{i}.jpg", JPG, "image/jpeg")) for i in range(6)]
    assert "hasta 5" in c.post("/pedidos", data=BASE_FOTO, files=seis).json()["error"]
    falsa = [("fotos", ("virus.jpg", b"MZ\x90\x00" * 10, "image/jpeg"))]
    assert "no parece una foto" in c.post("/pedidos", data=BASE_FOTO, files=falsa).json()["error"]
    pdf = [("fotos", ("a.pdf", b"%PDF", "application/pdf"))]
    assert c.post("/pedidos", data=BASE_FOTO, files=pdf).status_code == 422


def test_mail_mal_escrito(entorno):
    c, _, _ = entorno
    foto = [("fotos", ("a.jpg", JPG, "image/jpeg"))]
    r = c.post("/pedidos", data=BASE_FOTO | {"email": "ana@gmail.col"}, files=foto).json()
    assert r["campo"] == "email" and "ana@gmail.com" in r["error"]
    r = c.post("/pedidos", data=BASE_FOTO | {"email": "ana@gmail.col", "email_revisado": "si"}, files=foto).json()
    assert r["campo"] == "email" and "no existe" in r["error"]          # aunque diga "está bien así", el DNS manda
    assert c.post("/pedidos", data=BASE_FOTO | {"email": "ana perez@gmail.com"}, files=foto).json()["campo"] == "email"
    assert c.post("/pedidos", data=BASE_FOTO | {"email": "Ana@GMAIL.com"}, files=foto).status_code == 201


def test_sugerencias_de_mail():
    casos = {"a@gmail.col": "a@gmail.com", "a@gmial.com": "a@gmail.com", "a@hotmail.con": "a@hotmail.com",
             "a@hotmial.com": "a@hotmail.com", "a@gmail.com.ar": "a@gmail.com", "a@yaho.com.ar": "a@yahoo.com.ar",
             "a@empresa.con": "a@empresa.com", "a@gmail.com": "", "a@hotmail.com.ar": "", "a@empresa.com.ar": "",
             "a@fibertel.com.ar": "", "a@unlam.edu.ar": "", "a@mail.com": "", "a@ymail.com": ""}
    for mail, esperado in casos.items():
        assert correo.sugerencia(mail) == esperado, mail


def test_cuadro_pide_direccion(entorno):
    c, _, _ = entorno
    datos = BASE_FOTO | {"producto": "rf-cuadro-ecocuero-20x30"}
    foto = [("fotos", ("a.jpg", JPG, "image/jpeg"))]
    assert c.post("/pedidos", data=datos, files=foto).json()["campo"] == "envio_calle"
    direccion = {"envio_calle": "Mitre", "envio_numero": "123", "envio_localidad": "Sarandí",
                 "envio_provincia": "Buenos Aires", "envio_cp": "1872", "envio_dni": "30111222"}
    assert c.post("/pedidos", data=datos | direccion, files=foto).status_code == 201


def test_precios_ajustables_por_admin(entorno):
    c, _, _ = entorno
    adm = {"Authorization": "Bearer adm"}
    assert c.post("/admin/precios", json={"rf-cuadro-ecocuero-20x30": 36900}).status_code == 401
    assert c.post("/admin/precios", json={"no-existe": 1000}, headers=adm).status_code == 400
    assert c.post("/admin/precios", json={"rf-cuadro-ecocuero-20x30": 5}, headers=adm).status_code == 400
    assert c.post("/admin/precios", json={"rf-cuadro-ecocuero-20x30": 36900}, headers=adm).status_code == 200
    precios = {p["id"]: p["precio"] for p in c.get("/catalogo").json()["productos"]}
    assert precios["rf-cuadro-ecocuero-20x30"] == 36900 and precios["rf-cuadro-ecocuero-40x30"] == 44_999
    datos = BASE_FOTO | {"producto": "rf-cuadro-ecocuero-20x30", "envio_calle": "Mitre", "envio_numero": "123",
                         "envio_localidad": "Sarandí", "envio_provincia": "Buenos Aires", "envio_cp": "1872",
                         "envio_dni": "30111222"}
    r = c.post("/pedidos", data=datos, files=[("fotos", ("a.jpg", JPG, "image/jpeg"))])
    assert c.get(f"/admin/pedidos/{r.json()['pedido']}", headers=adm).json()["precio"] == 36900
    catalogo.cargar_precios(pathlib.Path("no-existe.json"))     # no contaminar las otras pruebas
    assert catalogo.PRODUCTOS["rf-cuadro-ecocuero-20x30"].precio == 34_999


def test_retorno_de_mercado_libre_muestra_el_codigo(entorno):
    c, _, _ = entorno
    r = c.get("/ml/callback", params={"code": "TG-abc123-456", "state": "x"})
    assert r.status_code == 200 and 'value="TG-abc123-456"' in r.text and r.headers["cache-control"] == "no-store"
    malo = c.get("/ml/callback", params={"code": '"><script>alert(1)</script>'})
    assert "<script>alert" not in malo.text and "No llegó el permiso" in malo.text
    assert "denegado" in c.get("/ml/callback", params={"error": "access_denied", "error_description": "denegado"}).text
    assert c.post("/ml/notificaciones", json={"topic": "items"}).status_code == 200


def test_vigilante_ajusta_precio_por_el_proveedor_mas_caro(entorno, monkeypatch):
    c, _, f = entorno
    adm = {"Authorization": "Bearer adm"}
    costos = {"https://meli.la/1NfcY82": ("MLA1286998514", 25000, "", "Llega gratis mañana"),
              "https://meli.la/1pXSHDH": ("MLA1287237038", 32900, "", "Llega gratis mañana"),
              "https://meli.la/19apaYx": ("MLA1777339229", 17999, "urbancraft", "Llega mañana"),
              "https://meli.la/2m8y8ov": ("MLA3279050800", 18500, "urbancraft", "Llega mañana"),
              "https://meli.la/1fQNtPf": ("MLA1777336761", 23000, "urbancraft", "Llega mañana"),
              "https://meli.la/1UFxNbZ": ("MLA1777336759", 23000, "urbancraft", "Llega mañana")}

    def leer(url):
        iid, precio, vend, envio = costos[url]
        return {"error": "", "item_id": iid, "titulo": "t", "permalink": url, "precio": precio, "vendedor": vend,
                "activa": True, "envio": envio, "llega_manana": True, "gratis": "gratis" in envio}
    monkeypatch.setattr(vigilante, "leer", leer)
    assert c.post("/admin/vigilante").status_code == 401
    r = c.post("/admin/vigilante", params={"prueba": "true"}, headers=adm).json()
    assert len(r["lecturas"]) == 6 and r["precios"]["rf-cuadro-enmarcado-20x30"] == 24_999     # prueba: no ajusta
    pedido_pagado(c, f, "rf-pack-5", comision=0.08)                     # un cobro real en el que MP se llevó el 8 %
    r = c.post("/admin/vigilante", headers=adm).json()
    assert r["precios"]["rf-cuadro-enmarcado-20x30"] == 25_999          # (18500 + 5000) / 0,92 → $25.999 (el negro, más caro)
    assert r["precios"]["rf-cuadro-ecocuero-20x30"] == 34_999 and r["precios"]["rf-cuadro-ecocuero-40x30"] == 44_999
    assert r["precios"]["rf-cuadro-enmarcado-30x40"] == 30_999          # (23000 + 5000) / 0,92 → $30.999
    assert [t for t, _ in f["notis"] if t.startswith("💲")] == [
        "💲 Precio ajustado: rf-cuadro-enmarcado-20x30 (la más cara: Enmarcado color negro 20x30)",
        "💲 Precio ajustado: rf-cuadro-enmarcado-30x40 (la más cara: Enmarcado color madera 30x40)"]
    catalogo.cargar_precios(pathlib.Path("no-existe.json"))     # no contaminar las otras pruebas


def test_vigilante_no_avisa_por_una_lectura_sin_envio(entorno, monkeypatch):
    """19/10 07:56: ML mandó la tarjeta del enmarcado madera sin el dato de envío y llegó un aviso falso."""
    c, _, f = entorno
    adm = {"Authorization": "Bearer adm"}
    ids = {x["url"]: x.get("item_id") for x in vigilante.publicaciones()}
    madera = "https://meli.la/19apaYx"
    envio = {"texto": ""}

    def leer(url):
        texto = envio["texto"] if url == madera else "Llega mañana"
        return {"error": "", "item_id": ids[url], "titulo": "t", "permalink": url, "precio": 17999,
                "vendedor": "", "activa": True, "envio": texto or "sin datos de envío", "sin_envio": not texto,
                "llega_manana": "mañana" in texto, "gratis": False}
    monkeypatch.setattr(vigilante, "leer", leer)
    envios = lambda: [t for t, _ in f["notis"] if t.startswith("🚚")]
    for _ in range(vigilante.LECTURAS_SIN_ENVIO - 1):        # lecturas incompletas sueltas: sin aviso
        c.post("/admin/vigilante", headers=adm)
    assert envios() == []
    envio["texto"] = "Llega mañana"                           # vuelve el dato: se reinicia la cuenta
    c.post("/admin/vigilante", headers=adm)
    envio["texto"] = ""
    for _ in range(vigilante.LECTURAS_SIN_ENVIO - 1):
        c.post("/admin/vigilante", headers=adm)
    assert envios() == []
    c.post("/admin/vigilante", headers=adm)                    # ya son LECTURAS_SIN_ENVIO seguidas: avisa
    assert envios() == ["🚚 Enmarcado color madera 20x30: ML no muestra el envío"]
    envio["texto"] = "Llega el jueves"                         # un cambio real de envío avisa al instante
    monkeypatch.setattr(vigilante, "REPETIR_AVISO", 0)
    c.post("/admin/vigilante", headers=adm)
    assert envios()[-1] == '🚚 Enmarcado color madera 20x30: no dice "Llega gratis mañana"'
    catalogo.cargar_precios(pathlib.Path("no-existe.json"))     # no contaminar las otras pruebas


def test_enmarcado_pide_color_de_marco(entorno):
    c, _, _ = entorno
    datos = BASE_FOTO | {"producto": "rf-cuadro-enmarcado-20x30", "envio_calle": "Mitre", "envio_numero": "123",
                         "envio_localidad": "Sarandí", "envio_provincia": "Buenos Aires", "envio_cp": "1872",
                         "envio_dni": "30111222"}
    foto = [("fotos", ("a.jpg", JPG, "image/jpeg"))]
    assert c.post("/pedidos", data=datos, files=foto).json()["campo"] == "marco"
    assert c.post("/pedidos", data=datos | {"marco": "Dorado"}, files=foto).json()["campo"] == "marco"
    r = c.post("/pedidos", data=datos | {"marco": "Negro"}, files=foto)
    assert r.status_code == 201
    detalle = c.get(f"/admin/pedidos/{r.json()['pedido']}", headers={"Authorization": "Bearer adm"}).json()
    assert detalle["datos"]["marco"] == "Negro" and "Color del marco: Negro" in detalle["resumen"]


def test_bot_y_condiciones(entorno):
    c, _, _ = entorno
    assert c.post("/pedidos", data=BASE_CANCION | {"estilos": "Tango", "sitio_web": "spam"}).status_code == 422
    assert c.post("/pedidos", data=BASE_CANCION | {"estilos": "Tango", "acepto": ""}).json()["campo"] == "acepto"


def test_entrega(entorno):
    c, app, f = entorno
    pid = c.post("/pedidos", data=BASE_CANCION | {"estilos": "Bolero"}).json()["pedido"]
    f["pagos"]["7"] = {"id": 7, "status": "approved", "external_reference": pid, "currency_id": "ARS",
                       "transaction_amount": 26999}
    c.post("/mp/webhook?data.id=7&type=payment", json={}, headers=firmar("7"))
    assert c.post(f"/admin/pedidos/{pid}/entrega", files=[("archivos", ("x.mp3", b"ID3", "audio/mpeg"))]).status_code == 401
    r = c.post(f"/admin/pedidos/{pid}/entrega", headers={"Authorization": "Bearer adm"},
               files=[("archivos", ("Tu canción para Marta.mp3", b"ID3", "audio/mpeg"))])
    assert r.status_code == 200, r.text
    assert app.state.base.obtener(pid)["estado"] == "entregado"
    assert f["drive"].compartidos and any("está listo" in m[1] for m in f["mails"])


def test_conciliacion_encuentra_pago_sin_webhook(entorno):
    c, app, f = entorno
    pid = c.post("/pedidos", data=BASE_CANCION | {"estilos": "Pop"}).json()["pedido"]
    f["pagos"]["8"] = {"id": 8, "status": "approved", "external_reference": pid, "currency_id": "ARS",
                       "transaction_amount": 26999}
    app.state.conciliar()
    assert app.state.base.obtener(pid)["estado"] == "pagado"


def test_normalizar_whatsapp():
    n = avisos.normalizar_whatsapp
    assert n("11 15 2345 6789") == "5491123456789"
    assert n("011 2345-6789") == "5491123456789"
    assert n("+54 9 11 2345 6789") == "5491123456789"
    assert n("351 15 555 1234") == "5493515551234"
    assert n("0351 555-1234") == "5493515551234"


def test_firma_manifiesto_documentado():
    assert mp.firma_valida(SECRETO, firmar("ABC123")["x-signature"].replace(
        firmar("ABC123")["x-signature"], firmar("abc123")["x-signature"]), "req-1", "ABC123")


def _pagar(c, f, pid, monto, pago_id):
    f["pagos"][pago_id] = {"id": int(pago_id), "status": "approved", "external_reference": pid, "currency_id": "ARS",
                           "transaction_amount": monto}
    c.post(f"/mp/webhook?data.id={pago_id}&type=payment", json={}, headers=firmar(pago_id))


def test_revision_foto_un_cambio_y_aprobacion(entorno):
    c, app, f = entorno
    pid = c.post("/pedidos", data=BASE_FOTO | {"producto": "rf-foto-1"},
                 files=[("fotos", ("a.jpg", JPG, "image/jpeg"))]).json()["pedido"]
    _pagar(c, f, pid, 4999, "11")
    adm = {"Authorization": "Bearer adm"}
    r = c.post(f"/admin/pedidos/{pid}/vista-previa", headers=adm, files=[("archivos", ("a-vista-previa.jpg", JPG, "image/jpeg"))])
    assert r.status_code == 200, r.text
    p = app.state.base.obtener(pid)
    assert p["estado"] == "vista_previa" and p["vista_n"] == 1
    assert any("Mirá cómo quedó tu foto" in m[1] for m in f["mails"])
    t = p["cliente_token"]
    assert c.get(f"/revisar/{pid}?t=malo").status_code == 404
    pagina = c.get(f"/revisar/{pid}?t={t}")
    assert pagina.status_code == 200 and "Me encanta, aprobar" in pagina.text and "Te queda 1 cambio." in pagina.text
    c.post(f"/revisar/{pid}", data={"t": t, "accion": "cambio", "texto": "Más color en el vestido"})
    p = app.state.base.obtener(pid)
    assert p["estado"] == "cambio" and p["cambios"] == 1 and "vestido" in p["nota_cambio"]
    c.post(f"/admin/pedidos/{pid}/vista-previa", headers=adm, files=[("archivos", ("a-v2.jpg", JPG, "image/jpeg"))])
    r = c.post(f"/revisar/{pid}", data={"t": t, "accion": "cambio", "texto": "otro cambio más"})
    assert "Ya usaste los cambios" in r.text
    c.post(f"/revisar/{pid}", data={"t": t, "accion": "aprobar"})
    assert app.state.base.obtener(pid)["estado"] == "aprobado"
    r = c.post(f"/admin/pedidos/{pid}/entrega", headers=adm, files=[("archivos", ("a-final.jpg", JPG, "image/jpeg"))])
    assert r.status_code == 200 and app.state.base.obtener(pid)["estado"] == "entregado"


def test_cancion_tiene_cinco_cambios(entorno):
    c, app, f = entorno
    pid = c.post("/pedidos", data=BASE_CANCION | {"estilos": "Pop"}).json()["pedido"]
    _pagar(c, f, pid, 26999, "12")
    adm = {"Authorization": "Bearer adm"}
    t = app.state.base.obtener(pid)["cliente_token"]
    for i in range(5):
        c.post(f"/admin/pedidos/{pid}/vista-previa", headers=adm, files=[("archivos", (f"v{i}.mp3", b"ID3", "audio/mpeg"))])
        c.post(f"/revisar/{pid}", data={"t": t, "accion": "cambio", "texto": f"cambio número {i}"})
    assert app.state.base.obtener(pid)["cambios"] == 5
    c.post(f"/admin/pedidos/{pid}/vista-previa", headers=adm, files=[("archivos", ("v6.mp3", b"ID3", "audio/mpeg"))])
    assert "Ya usaste" in c.post(f"/revisar/{pid}", data={"t": t, "accion": "cambio", "texto": "uno más"}).text


def test_config_limpia_fin_de_linea_windows(monkeypatch):
    from app.config import cargar
    monkeypatch.setenv("MP_MODO", "produccion\r")
    monkeypatch.setenv("MP_ACCESS_TOKEN", "APP_USR-123\r")
    monkeypatch.setenv("MP_WEBHOOK_SECRET", "secreto\r")
    monkeypatch.setenv("SMTP_APP_PASSWORD", "abcd efgh\r")
    c = cargar()
    assert c.mp_modo == "produccion" and c.mp_access_token == "APP_USR-123"
    assert c.mp_webhook_secret == "secreto" and c.smtp_password == "abcdefgh"


def test_error_inesperado_al_crear_pago_devuelve_502(entorno, monkeypatch):
    c, app, f = entorno
    def explota(*a, **k):
        raise ValueError("Illegal header value")
    monkeypatch.setattr(mp, "crear_preferencia", explota)
    r = c.post("/pedidos", data=BASE_CANCION | {"estilos": "Pop"})
    assert r.status_code == 502 and "Mercado Pago" in r.json()["error"]
    p = app.state.base.listar()[0]
    assert p["estado"] == "cancelado" and "Illegal header" in p["error"]


def test_diagnostico_no_muestra_valores(entorno):
    c, app, f = entorno
    assert c.get("/admin/diagnostico").status_code == 401
    d = c.get("/admin/diagnostico", headers={"Authorization": "Bearer adm"}).json()
    assert d["mp_access_token"].startswith("ok (4 caracteres)") and "TEST" not in str(d)
    assert d["mp_webhook_secret"].startswith("ok") and d["caracteres_raros"] == []



def test_retencion_borra_copia_del_servidor_y_purga_a_los_30_dias(entorno):
    from app import flujo
    c, app, f = entorno
    base, cfg = app.state.base, app.state.cfg
    pid = c.post("/pedidos", data=BASE_FOTO, files=[("fotos", ("a.jpg", JPG, "image/jpeg"))]).json()["pedido"]
    carpeta = cfg.datos_dir / "subidas" / pid
    assert any(carpeta.iterdir())
    _pagar(c, f, pid, 14999, "21")
    assert not carpeta.exists()                       # ya está en Drive: el servidor no guarda copia
    adm = {"Authorization": "Bearer adm"}
    c.post(f"/admin/pedidos/{pid}/entrega", headers=adm, files=[("archivos", ("a-final.jpg", JPG, "image/jpeg"))])
    assert any("30 días" in m[2] for m in f["mails"] if "está listo" in m[1])
    assert flujo.purgar_vencidos(cfg, base, f["drive"]) == []          # recién entregado: no se toca
    base.actualizar(pid, entregado="2026-01-01T00:00:00+00:00")
    assert flujo.purgar_vencidos(cfg, base, f["drive"]) == [pid]
    p = base.obtener(pid)
    assert p["purgado"] and p["archivos"] == [] and p["drive_carpeta"] in f["drive"].en_papelera
    assert flujo.purgar_vencidos(cfg, base, f["drive"]) == []          # no se purga dos veces


def test_admin_contacto(entorno):
    c, app, f = entorno
    pid = c.post("/pedidos", data=BASE_FOTO, files=[("fotos", ("a.jpg", JPG, "image/jpeg"))]).json()["pedido"]
    adm = {"Authorization": "Bearer adm"}

    # 401 sin token
    assert c.patch(f"/admin/pedidos/{pid}/contacto", json={"email": "nuevo@gmail.com"}).status_code == 401

    # 404 no existe
    assert c.patch("/admin/pedidos/RF-9999/contacto", headers=adm, json={"email": "nuevo@gmail.com"}).status_code == 404

    # 422 formato de email inválido
    r = c.patch(f"/admin/pedidos/{pid}/contacto", headers=adm, json={"email": "invalido sin arroba"})
    assert r.status_code == 422 and r.json()["campo"] == "email"

    # 422 email que no recibe correo (gmail.col simulado)
    r = c.patch(f"/admin/pedidos/{pid}/contacto", headers=adm, json={"email": "ana@gmail.col"})
    assert r.status_code == 422 and r.json()["campo"] == "email"

    # 422 whatsapp inválido
    r = c.patch(f"/admin/pedidos/{pid}/contacto", headers=adm, json={"whatsapp": "123"})
    assert r.status_code == 422 and r.json()["campo"] == "whatsapp"

    # 200 actualiza mail y whatsapp
    r = c.patch(f"/admin/pedidos/{pid}/contacto", headers=adm,
                json={"email": "nuevo.cliente@gmail.com", "whatsapp": "11 2345 6789"})
    assert r.status_code == 200
    p = app.state.base.obtener(pid)
    assert p["email"] == "nuevo.cliente@gmail.com"
    assert p["whatsapp"] == "5491123456789"


def test_admin_reenviar(entorno):
    c, app, f = entorno
    pid = c.post("/pedidos", data=BASE_FOTO, files=[("fotos", ("a.jpg", JPG, "image/jpeg"))]).json()["pedido"]
    precio = app.state.base.obtener(pid)["precio"]
    _pagar(c, f, pid, precio, "31")
    adm = {"Authorization": "Bearer adm"}

    # 401 sin token
    assert c.post(f"/admin/pedidos/{pid}/reenviar", json={"que": "vista_previa"}).status_code == 401

    # 422 que inválido
    r = c.post(f"/admin/pedidos/{pid}/reenviar", headers=adm, json={"que": "otro"})
    assert r.status_code == 422 and r.json()["campo"] == "que"

    # 409 sin vista previa
    assert c.post(f"/admin/pedidos/{pid}/reenviar", headers=adm, json={"que": "vista_previa"}).status_code == 409
    assert c.post(f"/admin/pedidos/{pid}/reenviar", headers=adm, json={"que": "entrega"}).status_code == 409

    # Generar vista previa
    c.post(f"/admin/pedidos/{pid}/vista-previa", headers=adm, files=[("archivos", ("a-v1.jpg", JPG, "image/jpeg"))])
    mails_antes = len(f["mails"])
    subidas_antes = len(f["drive"].subidos)

    # Reenviar vista previa: manda mail y aviso sin subir a Drive
    r = c.post(f"/admin/pedidos/{pid}/reenviar", headers=adm, json={"que": "vista_previa"})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert len(f["mails"]) == mails_antes + 1
    assert any("Mirá cómo quedó tu foto" in m[1] for m in f["mails"][mails_antes:])
    assert len(f["drive"].subidos) == subidas_antes   # no subió nada a Drive

    # Aprobar y entregar
    t = app.state.base.obtener(pid)["cliente_token"]
    c.post(f"/revisar/{pid}", data={"t": t, "accion": "aprobar"})
    c.post(f"/admin/pedidos/{pid}/entrega", headers=adm, files=[("archivos", ("a-fin.jpg", JPG, "image/jpeg"))])
    mails_antes = len(f["mails"])
    subidas_antes = len(f["drive"].subidos)

    # Reenviar entrega: manda mail y aviso sin subir a Drive
    r = c.post(f"/admin/pedidos/{pid}/reenviar", headers=adm, json={"que": "entrega"})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert len(f["mails"]) == mails_antes + 1
    assert any("está listo" in m[1] for m in f["mails"][mails_antes:])
    assert len(f["drive"].subidos) == subidas_antes


def test_admin_cambio_y_cambios_extra(entorno):
    c, app, f = entorno
    pid = c.post("/pedidos", data=BASE_FOTO, files=[("fotos", ("a.jpg", JPG, "image/jpeg"))]).json()["pedido"]
    precio = app.state.base.obtener(pid)["precio"]
    _pagar(c, f, pid, precio, "32")
    adm = {"Authorization": "Bearer adm"}

    # 409 si no está en vista_previa
    assert c.post(f"/admin/pedidos/{pid}/cambio", headers=adm, json={"texto": "Aclarar el fondo"}).status_code == 409
    assert c.post(f"/admin/pedidos/{pid}/cambios-extra", headers=adm, json={"cantidad": 1}).status_code == 409

    # Generar vista previa
    c.post(f"/admin/pedidos/{pid}/vista-previa", headers=adm, files=[("archivos", ("a-v1.jpg", JPG, "image/jpeg"))])

    # 422 si texto de cambio es menor a 5 caracteres
    r = c.post(f"/admin/pedidos/{pid}/cambio", headers=adm, json={"texto": "hola"})
    assert r.status_code == 422 and r.json()["campo"] == "texto"

    # Pedir cambio sin costo (por defecto sin_costo=True): suma 1 a cambios_extra y 1 a cambios
    r = c.post(f"/admin/pedidos/{pid}/cambio", headers=adm, json={"texto": "Aclarar un poco el fondo"})
    assert r.status_code == 200
    p = app.state.base.obtener(pid)
    assert p["estado"] == "cambio"
    assert p["cambios"] == 1
    assert p["cambios_extra"] == 1
    # Como es sin_costo, el cliente todavía tiene cambios disponibles (base 1 + 1 extra - 1 usado = 1 restante)
    assert flujo.cambios_max(p) - p["cambios"] == 1

    # 422 si cantidad de cambios-extra no es de 1 a 3
    r = c.post(f"/admin/pedidos/{pid}/cambios-extra", headers=adm, json={"cantidad": 0})
    assert r.status_code == 422 and r.json()["campo"] == "cantidad"
    r = c.post(f"/admin/pedidos/{pid}/cambios-extra", headers=adm, json={"cantidad": 5})
    assert r.status_code == 422 and r.json()["campo"] == "cantidad"
    r = c.post(f"/admin/pedidos/{pid}/cambios-extra", headers=adm, json={"cantidad": "uno"})
    assert r.status_code == 422 and r.json()["campo"] == "cantidad"

    # Sumar 2 cambios extra
    r = c.post(f"/admin/pedidos/{pid}/cambios-extra", headers=adm, json={"cantidad": 2})
    assert r.status_code == 200
    res = r.json()
    assert res["cambios_extra"] == 3
    assert res["quedan"] == 3  # base 1 + 3 extra - 1 usado = 3


def test_admin_pagos_y_costos(entorno, monkeypatch):
    c, app, fakes = entorno
    adm = {"Authorization": "Bearer adm"}

    # 1. 401 sin token
    assert c.get("/admin/pagos").status_code == 401
    assert c.get("/admin/costos").status_code == 401

    # 2. Setup pedidos con mp_pago
    base = app.state.base
    p1 = base.crear(id="RF-0001", marca="rf", producto="rf-pack-5", precio=500, nombre="Ana", email="ana@test.com", whatsapp="1123456789")
    base.marcar_pagado(p1["id"], "pago-100")
    p2 = base.crear(id="TC-0001", marca="tc", producto="tc-cancion", precio=500, nombre="Juan", email="juan@test.com", whatsapp="1198765432")
    base.marcar_pagado(p2["id"], "pago-200")

    # Pago falso con datos de pagador y tarjeta (para verificar que NO salgan)
    fakes["pagos"]["pago-100"] = {
        "status": "approved",
        "status_detail": "accredited",
        "payment_method_id": "account_money",
        "payment_type_id": "account_money",
        "installments": 1,
        "transaction_amount": 500.0,
        "fee_details": [{"type": "mercadopago_fee", "amount": 21.51, "fee_payer": "collector"}],
        "transaction_details": {"net_received_amount": 478.49},
        "transaction_amount_refunded": 0.0,
        "money_release_date": "2026-11-01T00:00:00Z",
        "money_release_status": "pending",
        "date_approved": "2026-10-14T01:00:00Z",
        # Datos prohibidos que no deben salir:
        "payer": {"email": "secreto@cliente.com", "identification": {"number": "12345678"}, "first_name": "Pedro"},
        "card": {"last_four_digits": "1234", "holder": {"name": "Pedro Perez"}},
    }

    llamadas_mp = []
    def mock_obtener_pago(cfg_, pid):
        llamadas_mp.append(pid)
        if pid == "pago-200":
            raise mp.ErrorMP("Mercado Pago 500: Internal error")
        return fakes["pagos"][pid]
    monkeypatch.setattr(mp, "obtener_pago", mock_obtener_pago)

    # 3. GET /admin/pagos
    r = c.get("/admin/pagos", headers=adm)
    assert r.status_code == 200
    pagos = r.json()
    assert len(pagos) >= 2

    pago_ok = next(p for p in pagos if p["pago"] == "pago-100")
    esperadas = {"pedido", "producto", "precio", "pago", "estado", "detalle", "medio", "tipo_medio",
                 "cuotas", "monto", "comisiones", "neto", "reembolsado", "liberacion", "aprobado"}
    assert set(pago_ok.keys()) == esperadas
    assert "payer" not in pago_ok
    assert "card" not in pago_ok
    assert pago_ok["neto"] == 478.49
    assert pago_ok["monto"] == 500.0
    assert pago_ok["comisiones"][0]["monto"] == 21.51

    # Un pago que falla no rompe la lista
    pago_fallido = next(p for p in pagos if p["pago"] == "pago-200")
    assert "error" in pago_fallido
    assert "Mercado Pago 500" in pago_fallido["error"]

    # 4. Caché: la segunda llamada a /admin/pagos no vuelve a llamar a MP para pago-100
    r2 = c.get("/admin/pagos", headers=adm)
    assert r2.status_code == 200
    assert llamadas_mp.count("pago-100") == 1

    # 5. GET /admin/costos sin vigilante
    r_costos = c.get("/admin/costos", headers=adm)
    assert r_costos.status_code == 200
    d_costos = r_costos.json()
    assert "productos" in d_costos
    assert "rf-cuadro-ecocuero-20x30" in d_costos["productos"]
    assert d_costos["proveedores"]["leido"] is None
    assert any(pub["publicado"] is None for pub in d_costos["proveedores"]["publicaciones"])

    # 6. GET /admin/costos con vigilante
    datos_dir = app.state.cfg.datos_dir
    p_estado = datos_dir / "proveedores-estado.json"
    p_estado.write_text(json.dumps({
        "costos": {"Ecocuero bastidor 20x30": 25000, "Enmarcado color madera 20x30": 17999}
    }), encoding="utf-8")

    r_costos_con = c.get("/admin/costos", headers=adm)
    assert r_costos_con.status_code == 200
    d_costos_con = r_costos_con.json()
    assert d_costos_con["proveedores"]["leido"] is not None
    pub_ecocuero = next(p for p in d_costos_con["proveedores"]["publicaciones"] if p["nombre"] == "Ecocuero bastidor 20x30")
    assert pub_ecocuero["publicado"] == 25000


def pedido_pagado(c, f, producto, comision, tipo="account_money", estado="approved", reembolsado=0.0):
    """Crea un pedido y lo paga por el webhook con un pago de MP que tiene esa comisión real (fee_details)."""
    datos = BASE_FOTO | {"producto": producto}
    pid = c.post("/pedidos", data=datos, files=[("fotos", ("a.jpg", JPG, "image/jpeg"))]).json()["pedido"]
    precio = catalogo.PRODUCTOS[producto].precio
    pago_id = str(100 + len(f["pagos"]))
    f["pagos"][pago_id] = {"id": int(pago_id), "status": "approved", "external_reference": pid, "currency_id": "ARS",
                           "transaction_amount": precio, "payment_type_id": tipo, "payment_method_id": tipo,
                           "installments": 1, "date_approved": "2026-10-14T10:00:00.000-03:00",
                           "fee_details": [{"type": "mercadopago_fee", "amount": round(precio * comision, 2),
                                            "fee_payer": "collector"}],
                           "transaction_details": {"net_received_amount": round(precio * (1 - comision), 2)},
                           "transaction_amount_refunded": reembolsado,
                           "money_release_date": "2026-11-01T10:00:00.000-03:00", "money_release_status": "pending"}
    c.post(f"/mp/webhook?data.id={pago_id}&type=payment", json={}, headers=firmar(pago_id))
    f["pagos"][pago_id]["status"] = estado
    return pid


def test_vigilante_usa_la_comision_real_de_mp(entorno, monkeypatch):
    c, app, f = entorno
    adm = {"Authorization": "Bearer adm"}
    costos = {"https://meli.la/1NfcY82": 25000, "https://meli.la/1pXSHDH": 32900,
              "https://meli.la/19apaYx": 17999, "https://meli.la/2m8y8ov": 18500,
              "https://meli.la/1fQNtPf": 23000, "https://meli.la/1UFxNbZ": 23000}
    ids = {x["url"]: x.get("item_id") for x in vigilante.publicaciones()}
    monkeypatch.setattr(vigilante, "leer", lambda url: {
        "error": "", "item_id": ids[url], "titulo": "t", "permalink": url, "precio": costos[url], "vendedor": "",
        "activa": True, "envio": "Llega gratis mañana", "llega_manana": True, "gratis": True})
    # 1. Sin cobros leídos no hay comisión real: no toca precios (nada de 8 % supuesto) y avisa
    r = c.post("/admin/vigilante", headers=adm).json()
    assert r["precios"]["rf-cuadro-enmarcado-20x30"] == 24_999
    assert any("sin ajustar" in t for t, _ in f["notis"])
    # 2. Cobros reales: 4,302 % (como los de la tienda). Un reembolso y uno rechazado no cuentan
    pedido_pagado(c, f, "rf-pack-5", comision=0.04302)
    pedido_pagado(c, f, "rf-pack-10", comision=0.30, reembolsado=24_999)
    r = c.post("/admin/vigilante", headers=adm).json()
    assert r["precios"]["rf-cuadro-enmarcado-20x30"] == 24_999          # (18500 + 5000) / 0,95698 = 24.556 → $24.999
    assert r["precios"]["rf-cuadro-ecocuero-20x30"] == 34_999            # costo igual al de base: mismo precio
    assert r["precios"]["rf-cuadro-enmarcado-30x40"] == 29_999          # (23000 + 5000) / 0,95698 = 29.259 → $29.999
    cm = c.get("/admin/costos", headers=adm).json()["comision_mp"]
    assert cm["porcentaje"] == 4.3 and cm["pagos"] == 1 and "Mercado Pago" in cm["fuente"]
    # 3. Si MP deja de responder, usa la última comisión real leída (con su fecha), no inventa ni deja de ajustar
    monkeypatch.setattr(mp, "obtener_pago", lambda cfg_, pid: (_ for _ in ()).throw(RuntimeError("MP caído")))
    app.state.cobros.cache.clear()
    costos["https://meli.la/2m8y8ov"] = 20000                           # el proveedor sube: hay que ajustar
    r = c.post("/admin/vigilante", headers=adm).json()
    assert r["precios"]["rf-cuadro-enmarcado-20x30"] == 26_999          # (20000 + 5000) / 0,95698 = 26.124 → $26.999
    catalogo.cargar_precios(pathlib.Path("no-existe.json"))     # no contaminar las otras pruebas


def test_precio_de_venta_con_la_tasa_real():
    regla = {"costo_base": 25000, "precio_base": 34999}
    assert vigilante.precio_de_venta(regla, 25000, 0.04302) == 34_999        # mismo costo: mismo precio
    assert vigilante.precio_de_venta(regla, 27000, 0.04302) == 37_999        # (27.000 + 8.493,3) / 0,95698 = 37.088 → $37.999
    assert vigilante.precio_de_venta({"ganancia_neta": 5000}, 17999, 0.04302) == 24_999


def test_admin_proveedores_auth_y_endpoints(entorno, monkeypatch):
    c, app, f = entorno
    adm = {"Authorization": "Bearer adm"}

    # 401 sin token
    assert c.get("/admin/proveedores").status_code == 401
    assert c.post("/admin/proveedores/Ecocuero bastidor 20x30/precio", json={"precio": 26000}).status_code == 401
    assert c.delete("/admin/proveedores/Ecocuero bastidor 20x30/precio").status_code == 401
    assert c.post("/admin/proveedores/pendientes/rf-cuadro-ecocuero-20x30/aprobar").status_code == 401
    assert c.post("/admin/proveedores/pendientes/rf-cuadro-ecocuero-20x30/rechazar").status_code == 401

    # 404 con publicación inexistente
    assert c.post("/admin/proveedores/Inexistente/precio", json={"precio": 20000}, headers=adm).status_code == 404
    assert c.delete("/admin/proveedores/Inexistente/precio", headers=adm).status_code == 404

    # 422 con precio inválido
    assert c.post("/admin/proveedores/Ecocuero bastidor 20x30/precio", json={"precio": -10}, headers=adm).status_code == 422
    assert c.post("/admin/proveedores/Ecocuero bastidor 20x30/precio", json={"precio": 0}, headers=adm).status_code == 422
    assert c.post("/admin/proveedores/Ecocuero bastidor 20x30/precio", json={"precio": "veinte"}, headers=adm).status_code == 422


def test_vigilante_historial_y_precio_a_mano(entorno, monkeypatch):
    c, app, f = entorno
    adm = {"Authorization": "Bearer adm"}
    pedido_pagado(c, f, "rf-pack-5", comision=0.04302)

    costos = {x["url"]: 25000 if "20x30" in x["nombre"] else 32900 for x in vigilante.publicaciones()}
    for x in vigilante.publicaciones():
        if "Enmarcado" in x["nombre"]:
            costos[x["url"]] = 17999 if "20x30" in x["nombre"] else 23000

    ids = {x["url"]: x.get("item_id") for x in vigilante.publicaciones()}
    monkeypatch.setattr(vigilante, "leer", lambda url: {
        "error": "", "item_id": ids[url], "titulo": "t", "permalink": url, "precio": costos[url], "vendedor": "",
        "activa": True, "envio": "Llega gratis mañana", "llega_manana": True, "gratis": True})

    # 1. Primera lectura: llena historial con 1 entrada por publicación
    c.post("/admin/vigilante", headers=adm)
    provs = c.get("/admin/proveedores", headers=adm).json()
    pub_eco = next(p for p in provs["publicaciones"] if p["nombre"] == "Ecocuero bastidor 20x30")
    assert len(pub_eco["historial"]) == 1
    assert pub_eco["historial"][0]["precio"] == 25000
    assert pub_eco["historial"][0]["fuente"] == "vigilante"
    assert pub_eco["ultima_lectura"]["precio"] == 25000

    # 2. Segunda lectura con mismo precio: no agrega entrada repetida
    c.post("/admin/vigilante", headers=adm)
    provs = c.get("/admin/proveedores", headers=adm).json()
    pub_eco = next(p for p in provs["publicaciones"] if p["nombre"] == "Ecocuero bastidor 20x30")
    assert len(pub_eco["historial"]) == 1

    # 3. Cargar precio a mano: se usa como costo y se ajusta en el momento
    # Con costo 22.000, el precio de venta baja de 34.999 a 31.999
    r = c.post("/admin/proveedores/Ecocuero bastidor 20x30/precio", json={"precio": 22000}, headers=adm).json()
    assert r["ok"] is True
    provs = c.get("/admin/proveedores", headers=adm).json()
    pub_eco = next(p for p in provs["publicaciones"] if p["nombre"] == "Ecocuero bastidor 20x30")
    assert pub_eco["a_mano"]["precio"] == 22000
    assert pub_eco["a_mano"]["leido_entonces"] == 25000
    assert pub_eco["historial"][-1]["precio"] == 22000
    assert pub_eco["historial"][-1]["fuente"] == "a mano"
    assert provs["productos"]["rf-cuadro-ecocuero-20x30"]["precio_vigente"] == 31_999

    # 4. Si el vigilante vuelve a leer 25.000 (igual a leido_entonces), el precio a mano se mantiene
    c.post("/admin/vigilante", headers=adm)
    provs = c.get("/admin/proveedores", headers=adm).json()
    pub_eco = next(p for p in provs["publicaciones"] if p["nombre"] == "Ecocuero bastidor 20x30")
    assert pub_eco["a_mano"] is not None
    assert provs["productos"]["rf-cuadro-ecocuero-20x30"]["precio_vigente"] == 31_999

    # 5. Si el vigilante lee un precio distinto (p.ej. 26.000), descarta a_mano y avisa por ntfy
    eco_url = next(x["url"] for x in vigilante.publicaciones() if x["nombre"] == "Ecocuero bastidor 20x30")
    costos[eco_url] = 26000
    c.post("/admin/vigilante", headers=adm)
    provs = c.get("/admin/proveedores", headers=adm).json()
    pub_eco = next(p for p in provs["publicaciones"] if p["nombre"] == "Ecocuero bastidor 20x30")
    assert pub_eco["a_mano"] is None
    assert any("precio a mano descartado" in t for t, _ in f["notis"])
    assert provs["productos"]["rf-cuadro-ecocuero-20x30"]["precio_vigente"] == 35_999

    # 6. Quitar precio a mano vía DELETE
    c.post("/admin/proveedores/Ecocuero bastidor 20x30/precio", json={"precio": 23000}, headers=adm)
    assert c.get("/admin/proveedores", headers=adm).json()["publicaciones"][0]["a_mano"] is not None
    c.delete("/admin/proveedores/Ecocuero bastidor 20x30/precio", headers=adm)
    assert c.get("/admin/proveedores", headers=adm).json()["publicaciones"][0]["a_mano"] is None


def test_vigilante_pendiente_aprobar_y_rechazar(entorno, monkeypatch):
    c, app, f = entorno
    adm = {"Authorization": "Bearer adm"}
    pedido_pagado(c, f, "rf-pack-5", comision=0.04302)

    costos = {x["url"]: 25000 if "20x30" in x["nombre"] else 32900 for x in vigilante.publicaciones()}
    for x in vigilante.publicaciones():
        if "Enmarcado" in x["nombre"]:
            costos[x["url"]] = 17999 if "20x30" in x["nombre"] else 23000

    ids = {x["url"]: x.get("item_id") for x in vigilante.publicaciones()}
    monkeypatch.setattr(vigilante, "leer", lambda url: {
        "error": "", "item_id": ids[url], "titulo": "t", "permalink": url, "precio": costos[url], "vendedor": "",
        "activa": True, "envio": "Llega gratis mañana", "llega_manana": True, "gratis": True})

    c.post("/admin/vigilante", headers=adm)
    eco_url = next(x["url"] for x in vigilante.publicaciones() if x["nombre"] == "Ecocuero bastidor 20x30")

    # Salto de más de 40%: costo sube a 50.000 (el precio tendría que pasar de 34.999 a 61.999)
    costos[eco_url] = 50000
    f["notis"].clear()
    c.post("/admin/vigilante", headers=adm)

    provs = c.get("/admin/proveedores", headers=adm).json()
    prod_info = provs["productos"]["rf-cuadro-ecocuero-20x30"]
    assert prod_info["precio_vigente"] == 34_999      # no cambió
    assert prod_info["pendiente"] is not None
    assert prod_info["pendiente"]["nuevo"] == 61_999
    assert prod_info["pendiente"]["costo"] == 50_000
    assert any("Precio raro" in t for t, _ in f["notis"])

    # Rechazar el cambio: se limpia el pendiente y recuerda el costo rechazado
    c.post("/admin/proveedores/pendientes/rf-cuadro-ecocuero-20x30/rechazar", headers=adm)
    provs = c.get("/admin/proveedores", headers=adm).json()
    assert provs["productos"]["rf-cuadro-ecocuero-20x30"]["pendiente"] is None

    # Si se vuelve a leer con el mismo costo (50.000): no vuelve a avisar ni a dejarlo pendiente
    f["notis"].clear()
    c.post("/admin/vigilante", headers=adm)
    provs = c.get("/admin/proveedores", headers=adm).json()
    assert provs["productos"]["rf-cuadro-ecocuero-20x30"]["pendiente"] is None
    assert not any("Precio raro" in t for t, _ in f["notis"])

    # Si el costo cambia otra vez (p.ej. 55.000): se recalcula el pendiente y avisa
    costos[eco_url] = 55000
    c.post("/admin/vigilante", headers=adm)
    provs = c.get("/admin/proveedores", headers=adm).json()
    assert provs["productos"]["rf-cuadro-ecocuero-20x30"]["pendiente"]["costo"] == 55_000

    # Aprobar el pendiente: aplica el precio nuevo
    res_ap = c.post("/admin/proveedores/pendientes/rf-cuadro-ecocuero-20x30/aprobar", headers=adm).json()
    assert res_ap["ok"] is True
    provs = c.get("/admin/proveedores", headers=adm).json()
    assert provs["productos"]["rf-cuadro-ecocuero-20x30"]["pendiente"] is None
    assert provs["productos"]["rf-cuadro-ecocuero-20x30"]["precio_vigente"] == res_ap["aplicado"]["nuevo"]


def test_seguimiento_cuadro(entorno):
    c, app, f = entorno
    adm = {"Authorization": "Bearer adm"}

    # 1. Crear un pedido de cuadro
    datos_cuadro = BASE_FOTO | {
        "producto": "rf-cuadro-enmarcado-20x30",
        "marco": "Madera",
        "envio_calle": "San Martín", "envio_numero": "123", "envio_localidad": "Avellaneda",
        "envio_provincia": "Buenos Aires", "envio_cp": "1870", "envio_dni": "30111222"
    }
    r_ped = c.post("/pedidos", data=datos_cuadro, files=[("fotos", ("a.jpg", JPG, "image/jpeg"))])
    pid = r_ped.json()["pedido"]

    # 409: pedido en estado pendiente_pago
    r = c.post(f"/admin/pedidos/{pid}/seguimiento", json={"numero": "AR123456789"}, headers=adm)
    assert r.status_code == 409

    # Pasar a aprobado
    app.state.base.actualizar(pid, estado="aprobado")

    # 409: pedido de producto sin envío
    pid_foto = c.post("/pedidos", data=BASE_FOTO | {"producto": "rf-foto-1"}, files=[("fotos", ("a.jpg", JPG, "image/jpeg"))]).json()["pedido"]
    app.state.base.actualizar(pid_foto, estado="aprobado")
    assert c.post(f"/admin/pedidos/{pid_foto}/seguimiento", json={"numero": "AR123456789"}, headers=adm).status_code == 409

    # 422: número inválido (< 4 chars o con saltos de línea)
    assert c.post(f"/admin/pedidos/{pid}/seguimiento", json={"numero": "12"}, headers=adm).status_code == 422
    assert c.post(f"/admin/pedidos/{pid}/seguimiento", json={"numero": "12345\n678"}, headers=adm).status_code == 422

    # 422: url inválida (no https)
    assert c.post(f"/admin/pedidos/{pid}/seguimiento", json={"numero": "AR123456789", "url": "http://ej.com"}, headers=adm).status_code == 422

    # Caso exitoso: guarda, envía mail y aviso
    f["mails"].clear()
    f["notis"].clear()
    r = c.post(f"/admin/pedidos/{pid}/seguimiento", json={
        "numero": "AR123456789",
        "empresa": "Correo Argentino",
        "url": "https://correoargentino.com.ar/track"
    }, headers=adm)
    assert r.status_code == 200
    res = r.json()
    assert res["ok"] is True
    assert "AR123456789" in res["texto"]
    assert "Correo Argentino" in res["texto"]
    assert "https://correoargentino.com.ar/track" in res["texto"]
    assert res["texto"].startswith("¡Hola Ana Pérez! Tu cuadro del pedido RF-")

    # Verifica mail y ntfy
    assert len(f["mails"]) == 1
    para, asunto, cuerpo = f["mails"][0]
    assert para == "ana@mail.com"
    assert "está en camino" in asunto
    assert cuerpo == res["texto"]
    assert any("Cuadro en camino" in t for t, _ in f["notis"])

    # Campos guardados en BD y devueltos en GET /admin/pedidos
    p_bd = app.state.base.obtener(pid)
    assert p_bd["seguimiento"] == "AR123456789"
    assert p_bd["seguimiento_url"] == "https://correoargentino.com.ar/track"
    assert p_bd["cuadro_comprado"] is not None

    p_admin = next(p for p in c.get("/admin/pedidos", headers=adm).json() if p["id"] == pid)
    assert p_admin["seguimiento"] == "AR123456789"
    assert p_admin["seguimiento_url"] == "https://correoargentino.com.ar/track"
    assert p_admin["cuadro_comprado"] is not None

    # 409 al repetir sin reenviar=true
    r = c.post(f"/admin/pedidos/{pid}/seguimiento", json={"numero": "AR987654321"}, headers=adm)
    assert r.status_code == 409

    # Reenviar=true actualiza y vuelve a mandar
    f["mails"].clear()
    r = c.post(f"/admin/pedidos/{pid}/seguimiento", json={"numero": "AR987654321", "reenviar": True}, headers=adm)
    assert r.status_code == 200
    assert len(f["mails"]) == 1
    assert app.state.base.obtener(pid)["seguimiento"] == "AR987654321"



# ---------------- Revisión de Claude de la fase 3 (14/10) ----------------
def test_seguimiento_previa_no_guarda_ni_manda_y_whatsapp_propio(entorno):
    c, app, f = entorno
    adm = {"Authorization": "Bearer adm"}
    datos = BASE_FOTO | {"producto": "rf-cuadro-enmarcado-20x30", "marco": "Negro", "envio_calle": "Mitre",
                         "envio_numero": "1", "envio_localidad": "Sarandí", "envio_provincia": "Buenos Aires",
                         "envio_cp": "1872", "envio_dni": "30111222"}
    pid = c.post("/pedidos", data=datos, files=[("fotos", ("a.jpg", JPG, "image/jpeg"))]).json()["pedido"]
    app.state.base.actualizar(pid, estado="aprobado")
    f["mails"].clear()
    f["notis"].clear()
    cuerpo = {"numero": "AR123456789", "empresa": "Andreani"}
    previa = c.post(f"/admin/pedidos/{pid}/seguimiento", json=cuerpo | {"previa": True}, headers=adm).json()
    assert previa["previa"] and "AR123456789 (Andreani)" in previa["texto"]
    assert not f["mails"] and not f["notis"] and not app.state.base.obtener(pid).get("seguimiento")
    # Lo que se manda es exactamente lo que mostró la previa; el WhatsApp no dice "respondé este mail"
    r = c.post(f"/admin/pedidos/{pid}/seguimiento", json=cuerpo, headers=adm).json()
    assert r["texto"] == previa["texto"] and f["mails"][-1][2] == previa["texto"]
    link_wa = f["notis"][-1][1][0]["url"]
    assert "escribime" in urllib.parse.unquote(link_wa) and "respond" not in urllib.parse.unquote(link_wa)
    assert c.post(f"/admin/pedidos/{pid}/seguimiento", json=cuerpo | {"previa": True}, headers=adm).status_code == 200
    malo = {"numero": "AR123456789", "url": "https://ej.com/a b"}
    assert c.post(f"/admin/pedidos/{pid}/seguimiento", json=malo | {"reenviar": True}, headers=adm).status_code == 422


def test_precio_a_mano_no_se_pierde_si_coincide_con_una_revision(entorno, monkeypatch):
    """Una revisión tarda (lee 6 publicaciones). Si en ese rato se carga un precio a mano, no se tiene que perder."""
    c, app, f = entorno
    adm = {"Authorization": "Bearer adm"}
    pedido_pagado(c, f, "rf-pack-5", comision=0.04302)
    leyendo, seguir = threading.Event(), threading.Event()
    ids = {x["url"]: x.get("item_id") for x in vigilante.publicaciones()}

    def leer_lento(url):
        leyendo.set()
        seguir.wait(5)
        return {"error": "", "item_id": ids[url], "titulo": "t", "permalink": url, "precio": 20000, "vendedor": "",
                "activa": True, "envio": "Llega gratis mañana", "llega_manana": True, "gratis": True}
    monkeypatch.setattr(vigilante, "leer", leer_lento)
    revision = threading.Thread(target=lambda: c.post("/admin/vigilante", headers=adm))
    revision.start()
    assert leyendo.wait(5)
    a_mano = threading.Thread(target=lambda: c.post("/admin/proveedores/Ecocuero bastidor 20x30/precio",
                                                     json={"precio": 21000}, headers=adm))
    a_mano.start()
    seguir.set()
    revision.join(10)
    a_mano.join(10)
    pubs = c.get("/admin/proveedores", headers=adm).json()["publicaciones"]
    eco = next(p for p in pubs if p["nombre"] == "Ecocuero bastidor 20x30")
    assert eco["a_mano"] and eco["a_mano"]["precio"] == 21000
    costos_pub = c.get("/admin/costos", headers=adm).json()["proveedores"]["publicaciones"]
    assert next(p for p in costos_pub if p["nombre"] == "Ecocuero bastidor 20x30")["a_mano"] == 21000
    catalogo.cargar_precios(pathlib.Path("no-existe.json"))     # no contaminar las otras pruebas


def test_precios_a_mano_y_modos(entorno, monkeypatch):
    c, app, f = entorno
    adm = {"Authorization": "Bearer adm"}

    # 1. 401 sin token
    assert c.get("/admin/precios").status_code == 401
    assert c.post("/admin/precios/rf-foto-1", json={"precio": 6000}).status_code == 401

    # 2. 404 producto no existe
    assert c.post("/admin/precios/producto-fantasma", json={"precio": 1000}, headers=adm).status_code == 404

    # 3. 422 validaciones
    r = c.post("/admin/precios/rf-foto-1", json={"precio": 50}, headers=adm)
    assert r.status_code == 422 and r.json()["campo"] == "precio"
    r = c.post("/admin/precios/rf-foto-1", json={"precio": 1_000_001}, headers=adm)
    assert r.status_code == 422 and r.json()["campo"] == "precio"
    r = c.post("/admin/precios/rf-foto-1", json={"precio": "seis mil"}, headers=adm)
    assert r.status_code == 422 and r.json()["campo"] == "precio"
    # modo en producto sin proveedor
    r = c.post("/admin/precios/rf-foto-1", json={"modo": "auto"}, headers=adm)
    assert r.status_code == 422 and r.json()["campo"] == "modo"
    # ganancia neta fuera de rango
    r = c.post("/admin/precios/rf-cuadro-enmarcado-20x30", json={"modo": "auto", "ganancia_neta": -5}, headers=adm)
    assert r.status_code == 422 and r.json()["campo"] == "ganancia_neta"
    # sin precio ni modo
    r = c.post("/admin/precios/rf-foto-1", json={"otro": 123}, headers=adm)
    assert r.status_code == 422 and r.json()["campo"] == "precio"

    # 4. Precio a mano sin proveedor (rf-foto-1 a 6.500)
    p_orig = catalogo.PRODUCTOS["rf-foto-1"].precio
    r = c.post("/admin/precios/rf-foto-1", json={"precio": 6500}, headers=adm)
    assert r.status_code == 200
    res = r.json()
    assert res["id"] == "rf-foto-1" and res["precio"] == 6500 and res["con_proveedor"] is False
    assert catalogo.PRODUCTOS["rf-foto-1"].precio == 6500

    # GET /admin/precios lista productos e historial
    r_list = c.get("/admin/precios", headers=adm)
    assert r_list.status_code == 200
    d_list = r_list.json()
    assert len(d_list["productos"]) == len(catalogo.PRODUCTOS)
    p_foto = next(p for p in d_list["productos"] if p["id"] == "rf-foto-1")
    assert p_foto["precio"] == 6500
    assert len(d_list["historial"]) >= 1
    h_ultimo = d_list["historial"][-1]
    assert h_ultimo["producto"] == "rf-foto-1" and h_ultimo["antes"] == p_orig and h_ultimo["despues"] == 6500
    assert h_ultimo["quien"] == "a mano"

    # 5. Cuadro a fijo
    p_eco_orig = catalogo.PRODUCTOS["rf-cuadro-ecocuero-20x30"].precio
    r = c.post("/admin/precios/rf-cuadro-ecocuero-20x30", json={"precio": 36000}, headers=adm)
    assert r.status_code == 200
    res_eco = r.json()
    assert res_eco["precio"] == 36000
    assert res_eco["modo"] == "fijo"

    # Vigilante no toca el precio fijo y avisa una sola vez si el costo deja menos ganancia que la regla
    f["notis"].clear()
    pedido_pagado(c, f, "rf-pack-5", comision=0.08)  # comisión 8%
    pubs_info = vigilante.publicaciones()
    url_eco = next(x["url"] for x in pubs_info if x.get("producto") == "rf-cuadro-ecocuero-20x30")
    costos_mock = {url_eco: 32000}  # 36000 * 0.92 = 33120; 33120 - 32000 = 1120 < ganancia regla (ej 10000)

    ids = {x["url"]: x.get("item_id") for x in vigilante.publicaciones()}
    def mock_leer(url):
        return {"error": "", "item_id": ids.get(url, "MLA1"), "titulo": "t", "permalink": url, "precio": costos_mock.get(url, 20000),
                "vendedor": "ARTEYCOLORES", "activa": True, "envio": "Llega gratis mañana", "llega_manana": True, "gratis": True}
    monkeypatch.setattr(vigilante, "leer", mock_leer)

    # 1era revisión: avisa que la ganancia bajó
    c.post("/admin/vigilante", headers=adm)
    assert catalogo.PRODUCTOS["rf-cuadro-ecocuero-20x30"].precio == 36000  # no cambia
    avisos_fijo = [t for t, _ in f["notis"] if "precio fijo" in t.lower() or "ganancia" in t.lower()]
    assert len(avisos_fijo) == 1

    # 2da revisión con mismo costo: no repite aviso
    c.post("/admin/vigilante", headers=adm)
    avisos_fijo_2 = [t for t, _ in f["notis"] if "precio fijo" in t.lower() or "ganancia" in t.lower()]
    assert len(avisos_fijo_2) == 1

    # 6. Volver a automático con ganancia propia (recalcula)
    r = c.post("/admin/precios/rf-cuadro-ecocuero-20x30", json={"modo": "auto", "ganancia_neta": 15000}, headers=adm)
    assert r.status_code == 200
    res_auto = r.json()
    assert res_auto["modo"] == "auto"
    assert res_auto["ganancia_neta"] == 15000
    assert res_auto["ganancia_origen"] == "a mano"
    assert catalogo.PRODUCTOS["rf-cuadro-ecocuero-20x30"].precio > 36000

    # 7. Volver a regla predeterminada
    r = c.post("/admin/precios/rf-cuadro-ecocuero-20x30", json={"modo": "auto", "ganancia_neta": None}, headers=adm)
    assert r.status_code == 200
    res_regla = r.json()
    assert res_regla["modo"] == "auto"
    assert res_regla["ganancia_origen"] == "regla"

    # Restaurar
    catalogo.cargar_precios(pathlib.Path("no-existe.json"))


def test_fechas_pedidos_recordatorios_y_baja(entorno, monkeypatch):
    c, app, f = entorno
    adm = {"Authorization": "Bearer adm"}
    base = app.state.base
    cfg = app.state.cfg

    # 1. Sin permiso no guarda nada en fechas ni en datos del pedido
    datos_sin_permiso = BASE_FOTO | {
        "para_quien": "Abuela Rosa", "vinculo": "abuela", "ocasion": "cumpleaños",
        "fecha_tipo": "Cumpleaños", "fecha_dia": "15", "fecha_mes": "8",
    }
    r = c.post("/pedidos", data=datos_sin_permiso, files=[("fotos", ("a.jpg", JPG, "image/jpeg"))])
    assert r.status_code == 201
    pid_sp = r.json()["pedido"]
    p_sp = base.obtener(pid_sp)
    assert "fecha_dia" not in p_sp.get("datos", {})
    assert len(base.listar_fechas()) == 0

    # 2. Validaciones en crear_pedido con permiso
    # 31 de abril no existe -> 422 fecha_dia
    d_invalida = BASE_FOTO | {
        "para_quien": "Juan", "vinculo": "hermano", "ocasion": "cumpleaños",
        "fecha_tipo": "Cumpleaños", "fecha_dia": "31", "fecha_mes": "4", "fecha_permiso": "si"
    }
    r = c.post("/pedidos", data=d_invalida, files=[("fotos", ("a.jpg", JPG, "image/jpeg"))])
    assert r.status_code == 422 and r.json()["campo"] == "fecha_dia"

    # 30 de febrero no existe -> 422 fecha_dia
    d_feb30 = BASE_FOTO | {
        "para_quien": "Juan", "vinculo": "hermano", "ocasion": "cumpleaños",
        "fecha_tipo": "Cumpleaños", "fecha_dia": "30", "fecha_mes": "2", "fecha_permiso": "si"
    }
    r = c.post("/pedidos", data=d_feb30, files=[("fotos", ("a.jpg", JPG, "image/jpeg"))])
    assert r.status_code == 422 and r.json()["campo"] == "fecha_dia"

    # 29 de febrero SÍ vale
    d_feb29 = BASE_FOTO | {
        "para_quien": "Néstor", "vinculo": "papá", "ocasion": "cumpleaños",
        "fecha_tipo": "Cumpleaños", "fecha_dia": "29", "fecha_mes": "2", "fecha_permiso": "si"
    }
    r = c.post("/pedidos", data=d_feb29, files=[("fotos", ("a.jpg", JPG, "image/jpeg"))])
    assert r.status_code == 201

    # Tipo inválido
    d_tipo_malo = BASE_FOTO | {
        "para_quien": "Juan", "vinculo": "primo", "ocasion": "otra",
        "fecha_tipo": "Invento", "fecha_dia": "10", "fecha_mes": "5", "fecha_permiso": "si"
    }
    r = c.post("/pedidos", data=d_tipo_malo, files=[("fotos", ("a.jpg", JPG, "image/jpeg"))])
    assert r.status_code == 422 and r.json()["campo"] == "fecha_tipo"

    # fecha_otra > 40 chars
    d_otra_larga = BASE_FOTO | {
        "para_quien": "Juan", "vinculo": "primo", "ocasion": "otra",
        "fecha_tipo": "Otra fecha", "fecha_otra": "A" * 41, "fecha_dia": "10", "fecha_mes": "5", "fecha_permiso": "si"
    }
    r = c.post("/pedidos", data=d_otra_larga, files=[("fotos", ("a.jpg", JPG, "image/jpeg"))])
    assert r.status_code == 422 and r.json()["campo"] == "fecha_otra"

    # 3. Guardar con permiso
    d_ok = BASE_FOTO | {
        "nombre": "Carlos", "email": "carlos@test.com", "whatsapp": "1144445555",
        "para_quien": "María", "vinculo": "mamá", "ocasion": "cumpleaños",
        "fecha_tipo": "Cumpleaños", "fecha_dia": "20", "fecha_mes": "10", "fecha_permiso": "si"
    }
    r = c.post("/pedidos", data=d_ok, files=[("fotos", ("a.jpg", JPG, "image/jpeg"))])
    assert r.status_code == 201
    fechas_bd = base.listar_fechas()
    f_maria = next(x for x in fechas_bd if x["para_quien"] == "María")
    assert f_maria["dia"] == 20 and f_maria["mes"] == 10
    assert f_maria["tipo"] == "Cumpleaños"
    assert f_maria["permiso_texto"] == "v1"
    assert len(f_maria["baja_token"]) >= 24
    assert f_maria["ultimo_aviso_anio"] is None

    # 4. Recordatorio diario (D-56): solo pedidos cobrados, cuando faltan 15 días o menos, una vez por ocurrencia
    # Sin cobrar no sale
    f["mails"].clear()
    _antiguedad_fechas(base, "2025-01-01T00:00:00+00:00")
    assert revisar_recordatorios_fechas(cfg, base, date(2026, 10, 5)) == [] and not f["mails"]
    for fila in base.listar_fechas():
        base.actualizar(fila["pedido"], estado="pagado")
    f["mails"].clear()
    f["notis"].clear()

    # Si hoy es 5 de octubre de 2026 -> faltan 15 días para el 20 de octubre
    hoy_aviso = date(2026, 10, 5)
    enviados = revisar_recordatorios_fechas(cfg, base, hoy_aviso)
    assert any(x["para_quien"] == "María" for x in enviados)
    assert len(f["mails"]) == 1
    para, asunto, cuerpo = f["mails"][0]
    assert para == "carlos@test.com"
    assert "cumpleaños de maría" in asunto.lower()
    assert f_maria["baja_token"] in cuerpo
    assert any("Recordatorio" in t for t, _ in f["notis"])

    f_act = base.obtener_fecha_por_token(f_maria["baja_token"])
    assert f_act["ultimo_aviso_anio"] == 2026

    # Si se vuelve a correr el mismo día (o año): no se repite
    f["mails"].clear()
    f["notis"].clear()
    enviados_2 = revisar_recordatorios_fechas(cfg, base, hoy_aviso)
    assert not any(x["para_quien"] == "María" for x in enviados_2)
    assert len(f["mails"]) == 0 and len(f["notis"]) == 0

    # 5. El 29/2 en año no bisiesto cuenta como 28/2
    f_nestor = next(x for x in base.listar_fechas() if x["para_quien"] == "Néstor")
    hoy_nestor = date(2026, 2, 13)
    f["mails"].clear()
    enviados_n = revisar_recordatorios_fechas(cfg, base, hoy_nestor)
    assert any(x["para_quien"] == "Néstor" for x in enviados_n)
    assert len(f["mails"]) == 1

    # 6. GET /baja/{token} y POST /baja/{token}
    tok = f_maria["baja_token"]
    # GET no cambia nada
    r_get_baja = c.get(f"/baja/{tok}")
    assert r_get_baja.status_code == 200
    assert "Dejar de recibir recordatorios" in r_get_baja.text
    assert base.obtener_fecha_por_token(tok)["baja_en"] is None

    # POST sí da de baja
    r_post_baja = c.post(f"/baja/{tok}")
    assert r_post_baja.status_code == 200
    assert "Listo, no te vamos a escribir más" in r_post_baja.text
    f_baja = base.obtener_fecha_por_token(tok)
    assert f_baja["baja_en"] is not None

    # Token inválido -> 404
    assert c.get("/baja/token-trucho").status_code == 404
    assert c.post("/baja/token-trucho").status_code == 404

    # Con baja no sale
    base.marcar_aviso_fecha(f_maria["id"], None)
    f["mails"].clear()
    enviados_baja = revisar_recordatorios_fechas(cfg, base, hoy_aviso)
    assert not any(x["para_quien"] == "María" for x in enviados_baja)
    assert len(f["mails"]) == 0

    # 7. GET /admin/fechas con las fechas comerciales (las próximas: si la de este año pasó, la del que viene)
    from app.main import tercer_domingo
    assert tercer_domingo(2026, 10) == date(2026, 10, 18) and tercer_domingo(2026, 6) == date(2026, 6, 21)
    assert tercer_domingo(2026, 8) == date(2026, 8, 16)
    assert c.get("/admin/fechas").status_code == 401
    r_adm_fechas = c.get("/admin/fechas", headers=adm)
    assert r_adm_fechas.status_code == 200
    d_fechas = r_adm_fechas.json()
    assert "fechas" in d_fechas and "cantidades" in d_fechas and "fechas_comerciales" in d_fechas

    com = {fc["nombre"]: fc for fc in d_fechas["fechas_comerciales"]}
    hoy_real = datetime.now(timezone(timedelta(hours=-3))).date()
    for nombre_fc, (mes_fc, domingo) in {"Día de la Madre": (10, True), "Día del Padre": (6, True),
                                          "Día del Niño": (8, True), "San Valentín": (2, False),
                                          "Navidad": (12, False)}.items():
        d = date.fromisoformat(com[nombre_fc]["fecha"])
        assert d >= hoy_real and d.month == mes_fc and (d.weekday() == 6 if domingo else True), nombre_fc
    assert com["San Valentín"]["dia"] == 14 and com["Navidad"]["dia"] == 25


def test_pedido_con_origen_utm_y_historial(entorno):
    c, app, f = entorno
    cfg = app.state.cfg

    # 1. Pedido con origen UTM completo y válido
    origen_valido = {"source": "meta", "medium": "paid", "campaign": "ddm2026", "content": "P004"}
    datos = BASE_FOTO | {"producto": "rf-foto-1", "origen": json.dumps(origen_valido)}
    r = c.post("/pedidos", data=datos, files=[("fotos", ("a.jpg", JPG, "image/jpeg"))])
    assert r.status_code == 201
    pid = r.json()["pedido"]
    p = app.state.base.obtener(pid)
    assert p["datos"]["origen"] == origen_valido

    hist_txt = (cfg.datos_dir / "subidas" / pid / "historial.txt").read_text(encoding="utf-8")
    assert "Origen: source: meta · medium: paid · campaign: ddm2026 · content: P004" in hist_txt

    # 2. Pedido con caracteres no permitidos o > 60 chars: se descartan campos inválidos sin rechazar pedido
    origen_sucio = {
        "source": "meta",
        "medium": "paid<script>alert(1)</script>",  # inválido
        "campaign": "a" * 65,                      # > 60 chars
        "content": "P005"                           # válido
    }
    datos2 = BASE_FOTO | {"producto": "rf-foto-1", "origen": json.dumps(origen_sucio)}
    r2 = c.post("/pedidos", data=datos2, files=[("fotos", ("b.jpg", JPG, "image/jpeg"))])
    assert r2.status_code == 201
    pid2 = r2.json()["pedido"]
    p2 = app.state.base.obtener(pid2)
    assert p2["datos"]["origen"] == {"source": "meta", "content": "P005"}

    # 3. Pedido sin origen
    datos3 = BASE_FOTO | {"producto": "rf-foto-1"}
    r3 = c.post("/pedidos", data=datos3, files=[("fotos", ("c.jpg", JPG, "image/jpeg"))])
    assert r3.status_code == 201
    pid3 = r3.json()["pedido"]
    p3 = app.state.base.obtener(pid3)
    assert "origen" not in p3["datos"]


def _antiguedad_fechas(base, creado):
    """Las fechas se cargan "ahora": para probar recordatorios hace falta que se hayan cargado hace tiempo."""
    with base._con() as con:
        con.execute("UPDATE fechas SET creado=?", (creado,))


def test_recordatorio_ventana_compra_reciente_mail_caido_y_html(entorno, monkeypatch):
    c, app, f = entorno
    base, cfg = app.state.base, app.state.cfg
    datos = BASE_FOTO | {"nombre": "<b>Ana</b>", "email": "ana@test.com", "para_quien": "Mamá <script>",
                         "vinculo": "mamá", "fecha_tipo": "Cumpleaños", "fecha_dia": "20", "fecha_mes": "11",
                         "fecha_permiso": "si"}
    pid = c.post("/pedidos", data=datos, files=[("fotos", ("a.jpg", JPG, "image/jpeg"))]).json()["pedido"]
    base.actualizar(pid, estado="pagado")
    # Compró hace pocos días para esa misma fecha: el aviso queda para el año que viene
    _antiguedad_fechas(base, "2026-11-01T12:00:00+00:00")
    f["mails"].clear()
    assert revisar_recordatorios_fechas(cfg, base, date(2026, 11, 10)) == [] and not f["mails"]
    # Cargada hace mucho: ventana de 15 días (no hace falta que sea justo el día 15)
    _antiguedad_fechas(base, "2025-06-01T12:00:00+00:00")
    # Si el mail falla, no se marca y se reintenta otro día
    def falla(*a, **k):
        raise RuntimeError("SMTP caído")
    monkeypatch.setattr(avisos, "mandar_mail", falla)
    assert revisar_recordatorios_fechas(cfg, base, date(2026, 11, 8)) == []
    assert base.listar_fechas()[0]["ultimo_aviso_anio"] is None
    mails = []
    monkeypatch.setattr(avisos, "mandar_mail", lambda cfg_, para, asunto, texto, html=None, responder_a=None: mails.append(html))
    assert len(revisar_recordatorios_fechas(cfg, base, date(2026, 11, 9))) == 1     # faltan 11 días: sale
    assert base.listar_fechas()[0]["ultimo_aviso_anio"] == 2026
    assert "<script>" not in mails[0] and "&lt;script&gt;" in mails[0] and "&lt;b&gt;Ana" in mails[0]
    assert revisar_recordatorios_fechas(cfg, base, date(2026, 11, 12)) == []          # una vez por ocurrencia
    # Diciembre para una fecha de enero: se marca con el año de la fecha
    base.marcar_aviso_fecha(base.listar_fechas()[0]["id"], None)
    with base._con() as con:
        con.execute("UPDATE fechas SET dia=5, mes=1")
    assert len(revisar_recordatorios_fechas(cfg, base, date(2026, 12, 25))) == 1
    assert base.listar_fechas()[0]["ultimo_aviso_anio"] == 2027


def test_reintento_transferencia_y_aprobacion_a_mano(entorno):
    c, app, f = entorno
    assert c.get("/catalogo").json()["transferencia"] == {"alias": "tutiendita.ia", "cbu": "0000003100082867824654"}
    pid = c.post("/pedidos", data=BASE_CANCION | {"estilos": "Tango"}).json()["pedido"]
    precio = app.state.base.obtener(pid)["precio"]
    # reintentar con Mercado Pago: el mismo link guardado, sin pedir otra preferencia
    r = c.get(f"/pedidos/{pid}/pagar")
    assert r.status_code == 200 and r.json()["init_point"].endswith(pid) and len(f["prefs"]) == 1
    # el cliente avisa que transfirió: un solo aviso al celular aunque toque dos veces; el pedido sigue sin pagar
    r = c.post(f"/pedidos/{pid}/transferencia")
    assert r.status_code == 200 and r.json()["alias"] == "tutiendita.ia" and r.json()["monto"] == precio
    c.post(f"/pedidos/{pid}/transferencia")
    assert [t for t, _ in f["notis"]].count(f"💸 Transferencia avisada {pid}") == 1
    assert c.get(f"/pedidos/{pid}/estado").json()["transferencia_avisada"] is True
    assert app.state.base.obtener(pid)["estado"] == "pendiente_pago"
    # aprobar la transferencia: solo con el token de admin, y una sola vez
    assert c.post(f"/admin/pedidos/{pid}/transferencia").status_code == 401
    auth = {"Authorization": "Bearer adm"}
    r = c.post(f"/admin/pedidos/{pid}/transferencia", headers=auth)
    assert r.status_code == 200 and r.json()["estado"] == "pagado"
    p = app.state.base.obtener(pid)
    assert p["pago_medio"] == "transferencia" and not p["mp_pago"] and p["drive_url"]
    assert any(m[0] == "juan@mail.com" for m in f["mails"]) and "transferencia" in flujo.resumen(p)
    assert f"Pedido pagado {pid}" in [t for t, _ in f["notis"]]
    assert c.post(f"/admin/pedidos/{pid}/transferencia", headers=auth).status_code == 409
    assert c.get(f"/pedidos/{pid}/pagar").status_code == 409
    assert c.post(f"/pedidos/{pid}/transferencia").status_code == 409
    # los cobros y la comisión real de Mercado Pago no cuentan la transferencia
    assert all(x["pedido"] != pid for x in app.state.cobros.lista())


def test_aviso_de_pedido_sin_pagar_interesados_y_vencimiento(entorno):
    c, app, f = entorno
    base, auth = app.state.base, {"Authorization": "Bearer adm"}
    pid = c.post("/pedidos", data=BASE_CANCION | {"estilos": "Tango"}).json()["pedido"]
    app.state.conciliar()
    assert not [t for t, _ in f["notis"] if "sin pagar" in t]            # recién creado: todavía no
    hace = lambda **kw: (datetime.now(timezone.utc) - timedelta(**kw)).isoformat(timespec="seconds")
    base.actualizar(pid, creado=hace(minutes=45))
    app.state.conciliar()
    app.state.conciliar()
    sin_pagar = [a for t, a in f["notis"] if t == f"🛒 Pedido sin pagar {pid}"]
    assert len(sin_pagar) == 1                                           # una sola vez
    link = urllib.parse.unquote(sin_pagar[0][0]["url"])
    assert link.startswith("https://wa.me/5493515551234") and "tutiendita.ia" in link and pid in link
    # interesados: está; si después compra con el mismo mail, sale de la lista
    assert c.get("/admin/interesados").status_code == 401
    lista = c.get("/admin/interesados", headers=auth).json()
    assert [i["pedido"] for i in lista] == [pid] and lista[0]["email"] == "juan@mail.com"
    pid2 = c.post("/pedidos", data=BASE_CANCION | {"estilos": "Tango"}).json()["pedido"]
    f["pagos"]["77"] = {"id": 77, "status": "approved", "external_reference": pid2, "currency_id": "ARS",
                        "transaction_amount": base.obtener(pid2)["precio"]}
    c.post("/mp/webhook?data.id=77&type=payment", json={}, headers=firmar("77"))
    assert c.get("/admin/interesados", headers=auth).json() == []
    # vencimiento: con transferencia avisada se espera una semana; sin aviso, a las 72 h se cancela
    base.actualizar(pid, creado=hace(days=4), transferencia_avisada=hace(days=4))
    app.state.conciliar()
    assert base.obtener(pid)["estado"] == "pendiente_pago"
    base.actualizar(pid, transferencia_avisada=None)
    app.state.conciliar()
    assert base.obtener(pid)["estado"] == "cancelado"


def test_link_de_revision_en_el_dominio_de_la_marca(entorno):
    _, app, _ = entorno
    cfg = app.state.cfg
    p = {"id": "RF-0009", "marca": "rf", "cliente_token": "tok"}
    assert flujo.link_revision(cfg, p).startswith("https://ej.com/")          # web bajo el campus: como antes
    cfg.url_web_rf = "https://restauraciondefotos.com.ar"
    assert flujo.link_revision(cfg, p) == "https://restauraciondefotos.com.ar/revisar/RF-0009?t=tok"


def _token(link):
    return urllib.parse.parse_qs(urllib.parse.urlparse(link).query)["canje"][0]


def test_foto_de_regalo_a_los_30_minutos_y_formulario_sin_pago(entorno):
    c, app, f = entorno
    base = app.state.base
    hace = lambda **kw: (datetime.now(timezone.utc) - timedelta(**kw)).isoformat(timespec="seconds")
    pid = c.post("/pedidos", data=BASE_CANCION | {"estilos": "Tango"}).json()["pedido"]
    # con un pago en efectivo pendiente, el regalo espera (y el aviso al celular lo dice)
    f["pagos"]["31"] = {"id": 31, "status": "pending", "external_reference": pid, "currency_id": "ARS",
                        "transaction_amount": base.obtener(pid)["precio"]}
    base.actualizar(pid, creado=hace(minutes=35))
    app.state.conciliar()
    assert not [m for m in f["mails"] if "Pudiste completar" in m[1]]
    assert base.obtener(pid)["aviso_sin_pago"] and not base.obtener(pid)["regalo_enviado"]
    # el pago en efectivo se cayó: en la vuelta siguiente sale el mail con el link de regalo (una sola vez)
    f["pagos"]["31"]["status"] = "cancelled"
    app.state.conciliar()
    app.state.conciliar()
    regalo = [m for m in f["mails"] if "Pudiste completar" in m[1]]
    assert len(regalo) == 1 and regalo[0][0] == "juan@mail.com"
    texto = regalo[0][2]
    assert "te regalamos la restauración de una foto" in texto and "tutiendita.ia" in texto
    link = next(l for l in texto.split() if "canje=" in l)
    assert link.startswith("https://ej.com/tutienditaia/restauraciondefotos/?canje=")
    token = _token(link)
    assert c.get(f"/canje/{token}").json() == {"estado": "valido", "tipo": "regalo", "producto": "rf-foto-1",
                                                "nombre": catalogo.PRODUCTOS["rf-foto-1"].nombre, "marca": "rf"}
    # un regalo por mail y por WhatsApp: otro pedido sin pagar de la misma persona no recibe otro
    pid2 = c.post("/pedidos", data=BASE_CANCION | {"estilos": "Tango", "email": "otro@mail.com"}).json()["pedido"]
    base.actualizar(pid2, creado=hace(minutes=40))
    app.state.conciliar()
    assert len([m for m in f["mails"] if "Pudiste completar" in m[1]]) == 1
    assert base.obtener(pid2)["regalo_enviado"].startswith("no:")
    # el formulario con el link: el producto lo fija el link (1 foto), no se cobra y entra en producción
    r = c.post("/pedidos", data=BASE_FOTO | {"producto": "rf-pack-20", "canje": token},
               files=[("fotos", ("mama.jpg", JPG, "image/jpeg"))])
    assert r.status_code == 201 and r.json()["pagado"] is True
    rid = r.json()["pedido"]
    p = base.obtener(rid)
    assert p["producto"] == "rf-foto-1" and p["precio"] == 0 and p["estado"] == "pagado" and p["pago_medio"] == "regalo"
    assert p["drive_url"] and f"🎁 Pedido de regalo {rid}" in [t for t, _ in f["notis"]]
    assert c.get(f"/pedidos/{rid}/estado").json()["pago_medio"] == "regalo"
    assert all(x["pedido"] != rid for x in app.state.cobros.lista())
    # se usa una sola vez
    otra = c.post("/pedidos", data=BASE_FOTO | {"canje": token}, files=[("fotos", ("b.jpg", JPG, "image/jpeg"))])
    assert otra.status_code == 422 and otra.json()["campo"] == "canje"
    assert c.get(f"/canje/{token}").json()["estado"] == "usado"
    assert c.get("/canje/inventado").status_code == 404


def test_link_de_mercado_libre(entorno):
    c, app, f = entorno
    auth = {"Authorization": "Bearer adm"}
    assert c.post("/admin/canjes", json={"tipo": "mercadolibre", "producto": "tc-cancion", "orden": "2000012345"}).status_code == 401
    r = c.post("/admin/canjes", json={"tipo": "mercadolibre", "producto": "tc-cancion", "orden": "2000012345"}, headers=auth)
    assert r.status_code == 200 and r.json()["nuevo"] and r.json()["link"].startswith("https://ej.com/tutienditaia/tucancion/?canje=")
    otra_vez = c.post("/admin/canjes", json={"tipo": "mercadolibre", "producto": "tc-cancion", "orden": "2000012345"}, headers=auth)
    assert not otra_vez.json()["nuevo"] and otra_vez.json()["token"] == r.json()["token"]   # un link por orden
    cuadro = c.post("/admin/canjes", json={"tipo": "mercadolibre", "producto": "rf-cuadro-ecocuero-20x30", "orden": "9"},
                    headers=auth)
    assert cuadro.status_code == 422
    assert c.post("/admin/canjes", json={"tipo": "mercadolibre", "producto": "tc-cancion"}, headers=auth).status_code == 422
    token = r.json()["token"]
    r = c.post("/pedidos", data=BASE_CANCION | {"estilos": "Tango", "canje": token})
    assert r.status_code == 201 and r.json()["pagado"] is True
    p = app.state.base.obtener(r.json()["pedido"])
    assert p["pago_medio"] == "mercadolibre" and p["precio"] == 0 and p["estado"] == "pagado"
    assert "Compra de Mercado Libre" in flujo.resumen(p)
    assert f"Pedido de Mercado Libre {p['id']}" in [t for t, _ in f["notis"]]
    # vencido: no sirve
    vencido = app.state.base.crear_canje(token="viejo", tipo="mercadolibre", producto="rf-foto-1",
                                         vence="2020-01-01T00:00:00+00:00", origen="1")
    assert c.get("/canje/viejo").json()["estado"] == "vencido"
    r = c.post("/pedidos", data=BASE_FOTO | {"canje": "viejo"}, files=[("fotos", ("b.jpg", JPG, "image/jpeg"))])
    assert r.status_code == 422 and r.json()["campo"] == "canje"
