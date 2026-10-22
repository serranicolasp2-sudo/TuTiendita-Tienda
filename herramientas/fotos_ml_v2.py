"""Fotos de Mercado Libre v2 (19/10/2026): exporta, diagnostica y (con --subir) reemplaza las fotos de las publicaciones.

  python tienda/herramientas/fotos_ml_v2.py              exporta tienda/ml-fotos/v2/*.html a png/ (1200x1200)
  python tienda/herramientas/fotos_ml_v2.py --diagnostico además las pasa por POST /moderations/pictures/diagnostic
  python tienda/herramientas/fotos_ml_v2.py --subir      sube y asigna las fotos de PLAN a cada publicación

Las piezas salen de tienda/ml-fotos/v2/generar.py. La portada (primera foto) va sin texto ni logo: ML marca
text_logo en la foto principal. Las fotos que se conservan de la publicación actual se nombran "actual:N" (N = posición).
"""
import argparse
import base64
import json
import pathlib
import sys
import time

import httpx

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
V2 = AQUI.parent / "ml-fotos" / "v2"
PNG = V2 / "png"

# Qué fotos lleva cada publicación, en orden (la primera es la portada).
PLAN = {
    "rf-foto-1": ["rf-portada-foto", "rf-como-nueva", "rf-color", "rf-caras", "rf-pasos"],
    "rf-pack-5": ["rf-portada-pack", "rf-album", "rf-como-nueva", "rf-color", "rf-pasos"],
    "rf-pack-10": ["rf-portada-pack", "rf-album", "rf-como-nueva", "rf-caras", "rf-pasos"],
    "rf-pack-20": ["rf-portada-pack", "rf-album", "rf-como-nueva", "rf-color", "rf-pasos"],
    # Enmarcados: un ítem por color de marco (User Products, 19/10). La portada es la foto del cuadro de ese color.
    "rf-cuadro-enmarcado-20x30": ["actual:0", "rf-cuadro-enmarcado", "rf-caras"],
    "rf-cuadro-enmarcado-20x30-negro": ["actual:0", "rf-cuadro-enmarcado", "rf-caras"],
    "rf-cuadro-enmarcado-30x40": ["actual:0", "rf-cuadro-enmarcado", "rf-caras"],
    "rf-cuadro-enmarcado-30x40-negro": ["actual:0", "rf-cuadro-enmarcado", "rf-caras"],
    "rf-cuadro-ecocuero-20x30": ["actual:0", "rf-cuadro-ecocuero", "rf-como-nueva", "rf-caras"],
    "rf-cuadro-ecocuero-40x30": ["actual:0", "rf-cuadro-ecocuero", "rf-como-nueva", "rf-caras"],
    "tc-cancion": ["tc-portada-cancion", "tc-recibis", "tc-pasos"],
    "tc-combo": ["tc-portada-combo", "tc-recibis", "tc-pasos-combo", "rf-caras"],
}


def exportar():
    from playwright.sync_api import sync_playwright
    PNG.mkdir(exist_ok=True)
    with sync_playwright() as p:
        nav = p.chromium.launch(channel="chrome")
        pag = nav.new_page(viewport={"width": 1080, "height": 1080}, device_scale_factor=1200 / 1080)
        for html in sorted(V2.glob("*.html")):
            pag.goto(html.as_uri())
            pag.wait_for_load_state("networkidle")
            pag.evaluate("document.fonts.ready")
            destino = PNG / f"{html.stem}.png"
            pag.screenshot(path=str(destino), clip={"x": 0, "y": 0, "width": 1080, "height": 1080})
            print(f"exportada {destino.name}")
        nav.close()


def jpg(imagen: pathlib.Path) -> bytes:
    """La imagen en JPG de calidad alta: pesa un décimo del PNG y ML la procesa sin demoras."""
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.open(imagen).convert("RGB").save(buf, "JPEG", quality=92)
    return buf.getvalue()


def diagnostico(ml, imagen, categoria, titulo, tipo) -> list[str]:
    """Problemas que ML ve en la imagen (lista vacía = válida). Espera y reintenta si ML limita las consultas."""
    datos = "data:image/jpeg;base64," + base64.b64encode(jpg(imagen)).decode()
    for intento in range(6):
        try:
            r = httpx.post("https://api.mercadolibre.com/moderations/pictures/diagnostic", headers=ml.h, timeout=120,
                           json={"picture_url": datos, "context": {"category_id": categoria, "title": titulo,
                                                                   "picture_type": tipo}})
        except httpx.TimeoutException:
            time.sleep(5 * (intento + 1))
            continue
        if r.status_code in (429, 404) and intento < 5:      # 429: límite de consultas; 404 suelto: reintento
            time.sleep(60 * (intento + 1))
            continue
        if r.status_code != 200:
            return [f"sin dato: ML respondió {r.status_code}"]
        diag = [d for d in r.json().get("diagnostics", []) if d.get("picture_type") == tipo]
        return [f"{det['name']}: {det['wordings'][0]['value']}" for d in diag for det in d.get("detections", [])]
    raise RuntimeError("ML siguió limitando las consultas de diagnóstico")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--diagnostico", action="store_true")
    ap.add_argument("--subir", action="store_true")
    ap.add_argument("--solo", help="producto del PLAN (para subir una sola publicación)")
    ap.add_argument("--solo-portadas", action="store_true",
                    help="diagnostica solo la portada (ML limita mucho las consultas; las secundarias tienen reglas flexibles)")
    args = ap.parse_args()
    if not PNG.is_dir() or not (args.subir or args.diagnostico):
        exportar()
    if not (args.diagnostico or args.subir):
        return
    import precios_ml as pm
    ml = pm.ML()
    items = {}
    for it in ml.publicaciones():
        negro = any(a["id"] == "FRAME_COLOR" and a.get("value_name") == "Negro" for a in it["attributes"])
        items[f'{pm.producto_item(it)}{"-negro" if negro else ""}'] = it
    cache = PNG / "diagnostico.json"
    revisadas = {tuple(k.split("|")): v for k, v in (json.loads(cache.read_text(encoding="utf-8")) if cache.is_file() else {}).items()}
    orden = sorted(PLAN.items(), key=lambda kv: kv[1][0].startswith("actual"))
    for prod, fotos in orden:
        if args.solo and prod != args.solo:
            continue
        it = items.get(prod)
        if not it:
            print(f"! {prod}: no encontré la publicación")
            continue
        ok = True
        for k, nombre in enumerate(fotos):
            if nombre.startswith("actual:") or (args.solo_portadas and k > 0):
                continue
            tipo = "thumbnail" if k == 0 else "other"
            clave = (nombre, it["category_id"], tipo)
            if clave not in revisadas:
                revisadas[clave] = diagnostico(ml, PNG / f"{nombre}.png", it["category_id"], it["title"], tipo)
                cache.write_text(json.dumps({"|".join(k): v for k, v in revisadas.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
                time.sleep(60)
            problemas = revisadas[clave]
            ok &= not problemas
            print(f"{prod:27} {k}:{nombre:22} {tipo:9} {'OK' if not problemas else ' | '.join(problemas)}")
        if not args.subir:
            continue
        if not ok:
            print(f"  → {prod}: no subo nada porque ML marcó problemas")
            continue
        ids = []
        for nombre in fotos:
            if nombre.startswith("actual:"):
                ids.append(it["pictures"][int(nombre.split(":")[1])]["id"])
                continue
            for intento in range(5):                               # ML a veces responde 500 al subir: reintento
                r = httpx.post("https://api.mercadolibre.com/pictures/items/upload", headers=ml.h, timeout=180,
                               files={"file": (f"{nombre}.jpg", jpg(PNG / f"{nombre}.png"), "image/jpeg")})
                if r.status_code < 500:
                    break
                time.sleep(10 * (intento + 1))
            r.raise_for_status()
            ids.append(r.json()["id"])
        r = httpx.put(f"https://api.mercadolibre.com/items/{it['id']}", headers=ml.h, timeout=60,
                      json={"pictures": [{"id": i} for i in ids]})
        print(f"  → {prod} {it['id']}: {'fotos cambiadas' if r.status_code == 200 else f'ERROR {r.status_code}: {r.text[:300]}'}")


if __name__ == "__main__":
    main()
