"""Cuadro enmarcado en marco negro en Mercado Libre (19/10/2026).

  python tienda/herramientas/enmarcado_negro_ml.py           valida con /items/validate (no publica nada)
  python tienda/herramientas/enmarcado_negro_ml.py --crear   publica el negro y deja el de madera con su color

Las publicaciones son "User Products": cada color es un ítem aparte con el mismo family_name y su "Color del armazón"
(FRAME_COLOR, atributo que define la foto); ML los agrupa en una sola página con un selector de color. El negro copia
del de madera precio, stock, envío, disponibilidad, atributos y descripción. Fotos: cada uno con su cuadro de portada
y las dos piezas de restauración. En la descripción, "madera natural" pasa a "color madera" (D-40: no es madera maciza).
"""
import argparse
import sys

import httpx

import precios_ml as pm

API = "https://api.mercadolibre.com"
MADERA = {"MLA4079023186": "20x30", "MLA4079109344": "30x40"}
COLOR = {"madera": {"id": "283154", "name": "Marrón claro"}, "negro": {"id": "52049", "name": "Negro"}}
CORRECCION = ("• Marco en madera natural o negro con vidrio.", "• Marco color madera o negro (a tu elección) con vidrio.")


def atributos(item, color):
    salida = [{"id": a["id"], "value_id": a.get("value_id"), "value_name": a.get("value_name")}
              for a in item["attributes"] if a["id"] != "FRAME_COLOR" and (a.get("value_id") or a.get("value_name"))]
    return salida + [{"id": "FRAME_COLOR", "value_id": COLOR[color]["id"], "value_name": COLOR[color]["name"]}]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crear", action="store_true")
    args = ap.parse_args()
    ml = pm.ML()
    for iid, medida in MADERA.items():
        it = ml.get(f"/items/{iid}")
        fotos = [p["id"] for p in it["pictures"]]
        if len(fotos) != 4:
            sys.exit(f"{iid}: esperaba 4 fotos (madera, negro, cuadro, caras) y tiene {len(fotos)}. No toco nada.")
        desc = ml.get(f"/items/{iid}/description")["plain_text"].replace(*CORRECCION)
        envio = it["shipping"]
        nuevo = {
            "family_name": it["family_name"], "category_id": it["category_id"], "price": it["price"],
            "currency_id": it["currency_id"], "available_quantity": it["available_quantity"],
            "buying_mode": it["buying_mode"], "listing_type_id": it["listing_type_id"], "condition": it["condition"],
            "pictures": [{"id": f} for f in (fotos[1], fotos[2], fotos[3])],
            "attributes": atributos(it, "negro"),
            "shipping": {"mode": envio["mode"], "local_pick_up": envio["local_pick_up"],
                         "free_shipping": envio["free_shipping"]},
            "sale_terms": [{"id": s["id"], "value_name": s["value_name"]} for s in it.get("sale_terms", [])],
        }
        r = httpx.post(f"{API}/items/validate", headers=ml.h, json=nuevo, timeout=60)
        causas = r.json().get("cause", []) if r.status_code != 204 else []
        errores = [c for c in causas if c.get("type") != "warning"]
        print(f"{medida} negro: validación {'OK' if not errores else 'CON ERRORES'}"
              + "".join(f"\n  {c.get('type')}: {c.get('code')} ({c.get('message')})" for c in causas))
        if not args.crear or errores:
            continue
        r = httpx.post(f"{API}/items", headers=ml.h, json=nuevo, timeout=60)
        if r.status_code not in (200, 201):
            print(f"  ERROR al publicar: {r.status_code} {r.text[:600]}")
            continue
        negro = r.json()
        print(f"  publicado {negro['id']} ({negro.get('permalink')}) · familia «{negro.get('family_name')}»")
        r = httpx.post(f"{API}/items/{negro['id']}/description", headers=ml.h, json={"plain_text": desc}, timeout=60)
        print(f"  descripción: {r.status_code}")
        r = httpx.put(f"{API}/items/{iid}", headers=ml.h, timeout=60, json={
            "attributes": [{"id": "FRAME_COLOR", "value_id": COLOR['madera']['id'], "value_name": COLOR['madera']['name']}],
            "pictures": [{"id": f} for f in (fotos[0], fotos[2], fotos[3])]})
        print(f"  madera {iid}: color y fotos {r.status_code} {r.text[:300] if r.status_code != 200 else ''}")
        r = httpx.put(f"{API}/items/{iid}/description", headers=ml.h, json={"plain_text": desc}, timeout=60)
        print(f"  madera {iid}: descripción {r.status_code}")


if __name__ == "__main__":
    main()
