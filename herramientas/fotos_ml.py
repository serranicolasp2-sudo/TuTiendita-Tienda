"""Fotos para Mercado Libre de Tu Canción, sin datos de contacto ni precio (D-60).

  python tienda/herramientas/fotos_ml.py

ML desenfoca o modera las fotos con links, @usuarios o teléfonos ("Datos de contacto y personales") y el precio impreso
queda viejo cuando cambia el de la publicación. Este script toma las piezas base de la marca
(marca/tu-cancion/piezas/), les saca en el navegador la línea de precio y la del usuario, cambia "por WhatsApp" por
"por mensaje" (en ML se habla por la mensajería de ML) y guarda los PNG en tienda/ml-fotos/. No modifica las piezas.
"""
import pathlib

from playwright.sync_api import sync_playwright

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PIEZAS = RAIZ / "marca" / "tu-cancion" / "piezas"
SALIDA = RAIZ / "tienda" / "ml-fotos"
FOTOS = ["tc-post-dedicatoria-1080x1350", "tc-post-pasos-1080x1350", "tc-post-ocasiones-1080x1350"]

LIMPIAR = r"""() => {
  for (const s of [...document.querySelectorAll('span, p, div')]) {
    if (s.children.length) continue;
    const t = s.textContent;
    if (/\$\s?\d|@|\.com\.ar|https?:|wa\.me/i.test(t)) s.remove();
    else if (/por WhatsApp/i.test(t)) s.textContent = t.replace(/por WhatsApp/i, 'por mensaje');
  }
  const resto = document.body.innerText;
  return /\$\s?\d|@|\.com\.ar|WhatsApp/i.test(resto) ? 'QUEDÓ: ' + resto : 'ok';
}"""


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        nav = p.chromium.launch(channel="chrome")
        pag = nav.new_page(viewport={"width": 1080, "height": 1350})
        for nombre in FOTOS:
            pag.goto((PIEZAS / f"{nombre}.html").as_uri())
            pag.wait_for_load_state("networkidle")
            pag.evaluate("document.fonts.ready")
            res = pag.evaluate(LIMPIAR)
            destino = SALIDA / f"{nombre}-ml.png"
            pag.screenshot(path=str(destino), clip={"x": 0, "y": 0, "width": 1080, "height": 1350})
            print(f"{destino.name}: {res}")
        nav.close()


if __name__ == "__main__":
    main()
