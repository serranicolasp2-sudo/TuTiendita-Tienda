"""API oficial de Mercado Libre (sin navegador): la usa el vigilante de proveedores.

  python ml_api.py autorizar   una sola vez: autorizás la app con tu cuenta de ML (en tu navegador de siempre)
                               y el permiso queda guardado en el Escritorio (ml_token.json; se renueva solo)
  python ml_api.py probar      lee las publicaciones de proveedores.json y muestra título, vendedor, precio y envío

Claves en claves-tienda.txt: ML_APP_ID y ML_CLIENT_SECRET (de tu app en developers.mercadolibre.com.ar) y ML_CP
(código postal para calcular el envío; si falta, 1870). Guía: tienda/docs/CLAVES.md §7.
"""
import base64
import contextlib
import datetime
import hashlib
import json
import msvcrt
import re
import secrets
import sys
import time
import unicodedata
import webbrowser
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

import pedidos

TOKEN = pedidos.ESCRITORIO / "ml_token.json"
CANDADO = pedidos.PEDIDOS / "ml_token.lock"
AUTH = "https://auth.mercadolibre.com.ar/authorization"
API = "https://api.mercadolibre.com"
REDIRECT = "https://campuscfp401avellaneda.com.ar/tutienditaia/api/ml/callback"


class SinAutorizar(RuntimeError):
    pass


def credenciales() -> tuple[str, str]:
    c = pedidos.claves()
    if not c.get("ML_APP_ID") or not c.get("ML_CLIENT_SECRET"):
        raise SinAutorizar("Faltan ML_APP_ID y ML_CLIENT_SECRET en claves-tienda.txt (CLAVES.md §7)")
    return c["ML_APP_ID"], c["ML_CLIENT_SECRET"]


def codigo_postal() -> str:
    return pedidos.claves().get("ML_CP") or "1870"


# ---------------- permiso (OAuth con PKCE) ----------------
@contextlib.contextmanager
def candado():
    """ML acepta cada llave de renovación una sola vez: si el bot y un comando la renuevan a la vez, se pierde
    el permiso. El candado hace que renueve uno solo."""
    CANDADO.parent.mkdir(parents=True, exist_ok=True)
    with open(CANDADO, "a+") as f:
        f.seek(0)
        for _ in range(60):
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                time.sleep(1)
        else:
            raise RuntimeError("Otro proceso está renovando el permiso de ML hace más de un minuto")
        try:
            yield
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def _guardar(t: dict):
    t["vence"] = time.time() + int(t.get("expires_in", 21600)) - 600
    tmp = TOKEN.with_suffix(".tmp")
    tmp.write_text(json.dumps(t, indent=2), encoding="utf-8")
    tmp.replace(TOKEN)


def autorizar():
    app_id, secreto = credenciales()
    verificador = secrets.token_urlsafe(64)
    desafio = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()
    estado = secrets.token_urlsafe(12)
    url = AUTH + "?" + urlencode({"response_type": "code", "client_id": app_id, "redirect_uri": REDIRECT,
                                  "state": estado, "code_challenge": desafio, "code_challenge_method": "S256"})
    print("Se abre Mercado Libre en tu navegador. Iniciá sesión si te lo pide y tocá «Permitir».\n"
          "Después te muestra un código (o una página con ?code=… en la dirección).\n")
    print(url, "\n")
    webbrowser.open(url)
    pegado = input("Pegá acá el código, o la dirección completa de la página a la que te llevó: ").strip()
    q = parse_qs(urlparse(pegado).query)
    codigo = q.get("code", [pegado])[0].strip()
    if q.get("state") and q["state"][0] != estado:
        sys.exit("El permiso no corresponde a este pedido. Volvé a correr: python ml_api.py autorizar")
    r = httpx.post(f"{API}/oauth/token", timeout=30, headers={"Accept": "application/json"}, data={
        "grant_type": "authorization_code", "client_id": app_id, "client_secret": secreto, "code": codigo,
        "redirect_uri": REDIRECT, "code_verifier": verificador})
    if r.status_code != 200:
        sys.exit(f"ML rechazó el código ({r.status_code}): {r.json().get('message', r.text[:200])}. "
                 "Los códigos duran pocos minutos y sirven una sola vez: volvé a correr el comando.")
    with candado():
        _guardar(r.json())
    yo = get("/users/me")
    print(f"Listo: autorizado con la cuenta {yo.get('nickname')}. El permiso se renueva solo.")
    if "offline_access" not in r.json().get("scope", ""):
        print("Ojo: ML no dio 'offline_access'. Activá «Acceso offline» en la app (CLAVES.md §7) y volvé a autorizar.")


def _leer_token() -> dict:
    if not TOKEN.exists():
        raise SinAutorizar("Falta autorizar la API de ML: python ml_api.py autorizar")
    return json.loads(TOKEN.read_text(encoding="utf-8"))


def token() -> str:
    t = _leer_token()
    if time.time() < t.get("vence", 0):
        return t["access_token"]
    app_id, secreto = credenciales()
    with candado():
        t = _leer_token()                      # quizás otro proceso ya lo renovó mientras esperábamos
        if time.time() < t.get("vence", 0):
            return t["access_token"]
        r = httpx.post(f"{API}/oauth/token", timeout=30, headers={"Accept": "application/json"}, data={
            "grant_type": "refresh_token", "client_id": app_id, "client_secret": secreto,
            "refresh_token": t["refresh_token"]})
        if r.status_code != 200:
            raise SinAutorizar(f"ML no renovó el permiso ({r.status_code}). Volvé a autorizar: python ml_api.py autorizar")
        _guardar(r.json())                     # ML entrega una llave de renovación nueva en cada renovación
        return r.json()["access_token"]


def get(ruta: str, **params) -> dict:
    r = httpx.get(f"{API}{ruta}", params=params, timeout=30, headers={"Authorization": f"Bearer {token()}"})
    r.raise_for_status()
    return r.json()


# ---------------- lectura de una publicación ----------------
def _normal(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def resolver_item(prov: dict, cache: dict | None = None) -> str | None:
    """Número MLA… de la publicación: item_id del archivo, o el guardado, o buscándolo (por título o por el MLAU…)."""
    if prov.get("item_id"):
        return prov["item_id"]
    clave = prov["nombre"]
    if cache is not None and cache.get(clave):
        return cache[clave]
    item = None
    if prov.get("buscar"):
        r = get("/sites/MLA/search", q=prov["buscar"], limit=50)
        buscado = _normal(prov["buscar"])
        candidatos = [it for it in r.get("results", []) if _normal(it.get("title")) == buscado] or \
                     [it for it in r.get("results", []) if buscado in _normal(it.get("title"))]
        item = candidatos[0]["id"] if candidatos else None
    elif re.search(r"MLAU\d+", prov.get("url", "")):
        up = re.search(r"MLAU\d+", prov["url"]).group(0)
        try:
            ids = re.findall(r"\bMLA\d{6,}\b", json.dumps(get(f"/user-products/{up}")))
            item = ids[0] if ids else None
        except httpx.HTTPStatusError:
            item = None
    if item and cache is not None:
        cache[clave] = item
    return item


def envio_manana(item_id: str) -> tuple[bool, str]:
    """¿Llega mañana a ML_CP? La API cotiza el envío a precio de lista, sin los beneficios de la cuenta (Meli+):
    en la web puede figurar "gratis" aunque acá tenga costo. Por eso se controla el día, y el costo es informativo."""
    manana = datetime.date.today() + datetime.timedelta(days=1)
    try:
        opciones = get(f"/items/{item_id}/shipping_options", zip_code=codigo_postal()).get("options", [])
    except httpx.HTTPStatusError as e:
        return False, f"no pude calcular el envío ({e.response.status_code})"
    fechas = []
    for op in opciones:
        fecha = ((op.get("estimated_delivery_time") or {}).get("date") or "")[:10]
        if fecha:
            fechas.append((datetime.date.fromisoformat(fecha), op.get("cost") or 0))
    if not fechas:
        return False, "sin datos de envío"
    dia, costo = min(fechas)
    cuando = "mañana" if dia == manana else ("hoy" if dia < manana else f"el {dia.strftime('%d/%m')}")
    precio = "gratis" if not costo else f"${costo:,.0f} de lista".replace(",", ".")
    return dia <= manana, f"llega {cuando} ({precio})"


def _bloqueo(e: httpx.HTTPStatusError, que: str) -> str:
    if e.response.status_code == 403:
        return (f"ML no deja {que} (403). A la app le falta el permiso de lectura de publicaciones: activalo en "
                "developers.mercadolibre.com.ar → tu app → Permisos y volvé a autorizar (CLAVES.md §7).")
    return f"ML respondió {e.response.status_code} al {que}."


def leer(prov: dict, cache: dict | None = None) -> dict:
    try:
        item_id = resolver_item(prov, cache)
    except httpx.HTTPStatusError as e:
        return {"error": _bloqueo(e, "buscar la publicación")}
    if not item_id:
        return {"error": "No encontré la publicación (MLA…). Cargá su número en item_id de proveedores.json."}
    try:
        it = get(f"/items/{item_id}")
    except httpx.HTTPStatusError as e:
        return {"error": _bloqueo(e, f"leer la publicación {item_id}")}
    try:
        precio = get(f"/items/{item_id}/sale_price", context="channel_marketplace")["amount"]
    except (httpx.HTTPStatusError, KeyError, TypeError):
        precio = it.get("price")
    try:
        vendedor = get(f"/users/{it['seller_id']}").get("nickname", "")
    except httpx.HTTPStatusError:
        vendedor = ""
    llega, envio = envio_manana(item_id)
    return {"error": "", "item_id": item_id, "titulo": it.get("title", ""), "permalink": it.get("permalink", ""),
            "precio": round(precio) if precio else None, "vendedor": vendedor, "activa": it.get("status") == "active",
            "llega_manana": llega, "envio": envio}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1 and sys.argv[1] == "autorizar":
        autorizar()
    elif len(sys.argv) > 1 and sys.argv[1] == "probar":
        import proveedores
        yo = get("/users/me")
        print(f"Cuenta autorizada: {yo.get('nickname')} · CP para envíos: {codigo_postal()}")
        for prov in proveedores.publicaciones():
            r = leer(prov)
            if r["error"]:
                print(f"✗ {prov['nombre']}: {r['error']}")
            else:
                print(f"✓ {prov['nombre']}: {r['item_id']} «{r['titulo']}» · vendedor {r['vendedor']} · "
                      f"${r['precio']} · {r['envio']}")
    else:
        sys.exit(__doc__)
