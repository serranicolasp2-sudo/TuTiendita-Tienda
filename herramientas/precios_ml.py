"""Precios de Mercado Libre: que cada venta en ML deje lo mismo que la misma venta en la web (D-60).

  python tienda/herramientas/precios_ml.py             muestra precio web, precio ML actual, lo que queda y el precio
                                                       que corresponde (no cambia nada)
  python tienda/herramientas/precios_ml.py --aplicar   además cambia en ML los precios que no coinciden

La web no cambia: ahí no hay cargo de ML. En ML el precio sube hasta cubrir lo que ML descuenta. Solo datos reales:
  - precio web: el catálogo en vivo (lo ajusta el vigilante de proveedores);
  - comisión de Mercado Pago en la web: la real de los cobros (GET /admin/pagos, como la centralita; D-49);
  - cargo de ML: /sites/MLA/listing_prices para cada precio probado (porcentaje + costo fijo por unidad);
  - envío: desde cierto precio ML obliga envío gratis en los productos con Mercado Envíos y lo paga el vendedor;
    el costo sale de /users/{id}/shipping_options/free con las medidas del paquete cargadas en la publicación.
Si falta cualquiera de esos datos, no se cambia el precio de esa publicación.

Precio de ML = el menor terminado en 999 (D-53) con  precio − cargo ML − envío a cargo ≥ precio web × (1 − % MP).
El costo del proveedor no entra: es el mismo en los dos canales, así que la ganancia queda igual.
"""
import argparse
import json
import math
import pathlib
import sys
import unicodedata

import httpx

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parents[1] / "centralita"))

import ml_api   # noqa: E402
import pedidos  # noqa: E402

CATALOGO = "https://tucancion.com.ar/tutienditaia/api/catalogo"

# Costo fijo por unidad que la pantalla de ML mostró más alto que la API (15/10/2026, cuadro 30x40 a $29.999:
# "Costo por unidad vendida $3.470"; listing_prices decía $3.320). Se usa el mayor de los dos.
FIJO_VISTO_EN_ML = {3320: 3470}

# Títulos de publicar_ml.py → producto del catálogo (ML a veces cambia mayúsculas: se comparan normalizados)
TITULOS = {
    "cancion personalizada con tu historia regalo digital mp3": "tc-cancion",
    "cancion personalizada + video con fotos para regalar": "tc-combo",
    "restauracion de foto antigua danada digital alta calidad": "rf-foto-1",
    "pack 5 fotos antiguas restauradas digital alta calidad": "rf-pack-5",
    "pack 10 fotos antiguas restauradas retoque digital": "rf-pack-10",
    "pack 20 fotos antiguas restauradas digital album familiar": "rf-pack-20",
    "pack 20 fotos antiguas restauradas retoque digital": "rf-pack-20",
    "cuadro enmarcado 20x30 con tu foto restaurada regalo": "rf-cuadro-enmarcado-20x30",
    "cuadro enmarcado 30x40 con tu foto restaurada regalo": "rf-cuadro-enmarcado-30x40",
    "cuadro bastidor ecocuero 20x30 con foto restaurada": "rf-cuadro-ecocuero-20x30",
    "cuadro bastidor ecocuero 40x30 con foto restaurada": "rf-cuadro-ecocuero-40x30",
}


def normal(t: str) -> str:
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return " ".join(t.split())


# Desde el 19/10 los enmarcados tienen un ítem por color de marco (User Products) y ML suma el color al título
# ("… Regalo Negro"); el family_name queda sin color.
SUFIJOS_COLOR = (" marron claro", " negro")


def producto(texto: str) -> str | None:
    """Producto del catálogo a partir de un título o family_name de ML (con o sin el color al final)."""
    n = normal(texto)
    for suf in ("",) + SUFIJOS_COLOR:
        if n.endswith(suf) and TITULOS.get(n[: len(n) - len(suf)] if suf else n):
            return TITULOS[n[: len(n) - len(suf)] if suf else n]
    return None


def producto_item(it: dict) -> str | None:
    return producto(it.get("family_name") or it["title"]) or producto(it["title"])


def pesos(n) -> str:
    return f"${round(n):,}".replace(",", ".") if n is not None else "sin dato"


def porcentaje_mp() -> tuple[float, str]:
    """% real de MP con dinero en cuenta, de los cobros de la web (mismo cálculo que la centralita)."""
    from servicios import costos
    with pedidos.cliente() as c:
        r = c.get("/admin/pagos", timeout=30)
        r.raise_for_status()
        resumen = costos.agrupar_pagos_por_medio(r.json())
    pct = resumen.get("porcentaje_dinero_cuenta")
    if pct is None:
        raise RuntimeError("sin dato: no hay cobros aprobados con dinero en cuenta para saber el % real de MP")
    return pct, resumen.get("fuente") or ""


class ML:
    def __init__(self):
        self.h = {"Authorization": f"Bearer {ml_api.token()}"}
        self.uid = self.get("/users/me")["id"]
        self._cargos, self._envios = {}, {}

    def get(self, ruta, **params):
        r = httpx.get(f"{ml_api.API}{ruta}", params=params, headers=self.h, timeout=30)
        r.raise_for_status()
        return r.json()

    def publicaciones(self) -> list[dict]:
        ids = []
        for estado in ("active", "paused"):
            ids += self.get(f"/users/{self.uid}/items/search", status=estado, limit=100).get("results", [])
        return [self.get(f"/items/{i}") for i in dict.fromkeys(ids)]

    def cargo(self, precio: int, categoria: str, tipo: str) -> float:
        clave = (precio, categoria, tipo)
        if clave not in self._cargos:
            b = self.get("/sites/MLA/listing_prices", price=precio, category_id=categoria, listing_type_id=tipo)
            b = b[0] if isinstance(b, list) else b
            det = b.get("sale_fee_details") or {}
            fijo = float(det.get("fixed_fee") or 0)
            extra = FIJO_VISTO_EN_ML.get(round(fijo), fijo) - fijo
            self._cargos[clave] = float(b["sale_fee_amount"]) + extra
        return self._cargos[clave]

    def envio_a_cargo(self, item: dict, precio: int) -> float:
        """Lo que paga el vendedor por el envío gratis obligatorio a ese precio (0 si no es obligatorio)."""
        if (item.get("shipping") or {}).get("mode") != "me2":
            return 0.0
        attrs = {a["id"]: a.get("value_name") or "" for a in item.get("attributes", [])}
        try:
            alto, largo, ancho = (int(float(attrs[f"SELLER_PACKAGE_{k}"].split()[0]))
                                  for k in ("HEIGHT", "LENGTH", "WIDTH"))
            peso = int(float(attrs["SELLER_PACKAGE_WEIGHT"].split()[0]))
        except (KeyError, ValueError, IndexError):
            raise RuntimeError("sin dato: la publicación no tiene las medidas del paquete para calcular el envío")
        clave = (alto, largo, ancho, peso, precio, item["listing_type_id"])
        if clave not in self._envios:
            b = self.get(f"/users/{self.uid}/shipping_options/free", dimensions=f"{largo}x{ancho}x{alto},{peso}",
                         item_price=precio, listing_type_id=item["listing_type_id"], mode="me2", condition="new",
                         logistic_type=(item.get("shipping") or {}).get("logistic_type") or "xd_drop_off",
                         verbose="true")
            cob = (b.get("coverage") or {}).get("all_country") or {}
            obligatorio = ((cob.get("discount") or {}).get("type") == "mandatory")
            self._envios[clave] = float(cob.get("list_cost") or 0) if obligatorio else 0.0
        return self._envios[clave]

    def queda(self, item: dict, precio: int) -> tuple[float, float, float]:
        c = self.cargo(precio, item["category_id"], item["listing_type_id"])
        e = self.envio_a_cargo(item, precio)
        return precio - c - e, c, e

    def precio_justo(self, item: dict, objetivo: float) -> int:
        p = math.ceil((objetivo + 1) / 1000) * 1000 - 1
        while p <= objetivo * 3:
            if self.queda(item, p)[0] >= objetivo:
                return p
            p += 1000
        raise RuntimeError("no encontré un precio hasta 3 veces el de la web")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aplicar", action="store_true", help="cambia en ML los precios que no coinciden")
    args = ap.parse_args()

    web = {p["id"]: p["precio"] for p in httpx.get(CATALOGO, timeout=30).json()["productos"]}
    pct, fuente = porcentaje_mp()
    print(f"Comisión real de Mercado Pago en la web: {pct:.2f} % ({fuente})\n".replace(".", ",", 1))
    ml = ML()
    cambios = []
    for it in ml.publicaciones():
        prod = producto_item(it)
        if not prod or prod not in web:
            print(f"? {it['id']} «{it['title']}»: no sé qué producto es. No lo toco.")
            continue
        objetivo = web[prod] * (1 - pct / 100)
        try:
            ahora, c_ahora, e_ahora = ml.queda(it, int(it["price"]))
            nuevo = ml.precio_justo(it, objetivo)
            queda_nuevo, c_nuevo, e_nuevo = ml.queda(it, nuevo)
        except Exception as e:
            print(f"! {it['id']} {prod}: {e}. No lo toco.")
            continue
        marca = "  ok" if nuevo == it["price"] else "  ⚠"
        print(f"{marca} {prod:<27} {it['id']} [{it['status']}]  web {pesos(web[prod])} → en la web te quedan "
              f"{pesos(objetivo)}")
        print(f"       en ML hoy {pesos(it['price'])}: cargo {pesos(c_ahora)} + envío {pesos(e_ahora)} → te quedan "
              f"{pesos(ahora)} ({pesos(ahora - objetivo)} contra la web)")
        if nuevo != it["price"]:
            print(f"       precio ML que corresponde {pesos(nuevo)}: cargo {pesos(c_nuevo)} + envío {pesos(e_nuevo)} → "
                  f"te quedan {pesos(queda_nuevo)}")
            cambios.append((it, prod, nuevo))
    if not args.aplicar:
        print(f"\n{len(cambios)} precios para cambiar. Para aplicarlos: --aplicar")
        return
    print()
    for it, prod, nuevo in cambios:
        r = httpx.put(f"{ml_api.API}/items/{it['id']}", headers=ml.h, json={"price": nuevo}, timeout=30)
        estado = "cambiado" if r.status_code == 200 else f"ERROR {r.status_code}: {r.text[:300]}"
        print(f"{prod:<27} {it['id']} {pesos(it['price'])} → {pesos(nuevo)}: {estado}")


if __name__ == "__main__":
    main()
