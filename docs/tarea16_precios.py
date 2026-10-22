"""Tarea 16, paso 1 (lo escribió Claude; lo corre Antigravity después de terminar la tarea 15).

Precios reales (D-20: se terminan los precios de prueba de $500):
  - tienda/app/catalogo.py: rf-foto-1 $5.000 y tc-cancion $27.000 (valores de base).
  - web/restauraciondefotos/index.html e index-base.html: los precios escritos pasan a ser el valor de arranque real y
    quedan marcados con data-precio (los pinta tienda.js con el precio del servidor; ver D-51).
Las páginas de Tu Canción, movil.js y tienda.js ya los tienen (los dejó Claude el 14/10).

Uso:  python tienda/docs/tarea16_precios.py
Si un texto no coincide, frena sin escribir nada (avisá y no lo arregles a mano). Correrlo dos veces no cambia nada.
"""
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = pathlib.Path(__file__).resolve().parents[2]
B28 = "<b style=\"font-family: 'Bricolage Grotesque', 'Arial Narrow', sans-serif; font-weight: 800; font-size: 28px; letter-spacing: -0.02em\">"
P14 = '<p style="margin: 0; font-size: 14px; color: #5A5345">'

ARCHIVOS = {
    RAIZ / "tienda/app/catalogo.py": [
        ('Producto("rf-foto-1", "rf", "Restauración de 1 foto", 500,', 'Producto("rf-foto-1", "rf", "Restauración de 1 foto", 5_000,', 1),
        ('Producto("tc-cancion", "tc", "Canción con tu historia", 500,', 'Producto("tc-cancion", "tc", "Canción con tu historia", 27_000,', 1),
    ],
}
FOTOS = [
    ("Desde $500 por foto, vista previa", "Desde $5.000 por foto, vista previa", 2),
    (B28 + "$500</b> por foto · Packs desde $15.000",
     B28.replace("<b ", '<b data-precio="rf-foto-1" ') + '$5.000</b> por foto · Packs desde <span data-precio="rf-pack-5">$15.000</span>', 1),
    ('<div class="rf-card-precio">$500</div>', '<div class="rf-card-precio" data-precio="rf-foto-1">$5.000</div>', 1),
    (P14 + "$3.000 por foto · Hasta 5 fotos.</p>",
     P14 + '<span data-precio="rf-pack-5" data-por-foto="5">$3.000</span> por foto · Hasta 5 fotos.</p>', 1),
    (P14 + "$2.500 por foto · Hasta 10 fotos.</p>",
     P14 + '<span data-precio="rf-pack-10" data-por-foto="10">$2.500</span> por foto · Hasta 10 fotos.</p>', 1),
    (P14 + "$1.995 por foto · Hasta 20 fotos.</p>",
     P14 + '<span data-precio="rf-pack-20" data-por-foto="20">$1.995</span> por foto · Hasta 20 fotos.</p>', 1),
    ('<div class="rf-card-precio" style="color: #D7301F; margin-top: 10px">$59.900</div>',
     '<div class="rf-card-precio" data-precio="tc-combo" style="color: #D7301F; margin-top: 10px">$59.900</div>', 1),
    ('color: #D7301F">Restauración de 1 foto — $500</span>',
     'color: #D7301F">Restauración de 1 foto — <span data-precio="rf-foto-1">$5.000</span></span>', 1),
    ('"rf-foto-1": { nombre: "Restauración de 1 foto", precio: "$500",',
     '"rf-foto-1": { nombre: "Restauración de 1 foto", precio: "$5.000",', 1),
    ('    resumenProd.textContent = cfg.nombre + " — " + (precioCard ? precioCard.textContent : cfg.precio);',
     '    // El resumen lleva el precio vigente (lo pinta tienda.js; el texto es el valor de arranque)\n'
     '    resumenProd.textContent = cfg.nombre + " — ";\n'
     '    var spanPrecio = document.createElement("span");\n'
     '    spanPrecio.setAttribute("data-precio", id);\n'
     '    spanPrecio.textContent = precioCard ? precioCard.textContent : cfg.precio;\n'
     '    resumenProd.appendChild(spanPrecio);\n'
     '    if (window.Tienda && window.Tienda.pintarPrecios) window.Tienda.pintarPrecios(resumenProd);', 1),
]
for n in ("index.html", "index-base.html"):
    ARCHIVOS[RAIZ / "web/restauraciondefotos" / n] = FOTOS

nuevos = {}
for ruta, cambios in ARCHIVOS.items():
    t = ruta.read_text(encoding="utf-8")
    if all(t.count(nuevo) >= 1 for _, nuevo, _ in cambios):
        print(f"{ruta.relative_to(RAIZ)}: ya estaba aplicado")
        continue
    for viejo, nuevo, cantidad in cambios:
        if t.count(viejo) != cantidad:
            sys.exit(f"FRENO: en {ruta.relative_to(RAIZ)} no encuentro {cantidad} vez/veces: {viejo[:80]!r}. No escribí nada.")
        t = t.replace(viejo, nuevo)
    if ruta.suffix == ".html" and "$500" in t:
        sys.exit(f"FRENO: en {ruta.relative_to(RAIZ)} queda un $500. No escribí nada.")
    nuevos[ruta] = t

for ruta, t in nuevos.items():
    ruta.write_text(t, encoding="utf-8", newline="\n")
    print(f"{ruta.relative_to(RAIZ)}: listo")
