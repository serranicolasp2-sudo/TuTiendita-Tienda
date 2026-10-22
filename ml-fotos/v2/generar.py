"""Genera las piezas HTML de las fotos de Mercado Libre v2 (19/10/2026).

  python tienda/ml-fotos/v2/generar.py      escribe los .html en esta carpeta
  python tienda/herramientas/fotos_ml_v2.py exporta a PNG 1200x1200 y los diagnostica con la API de ML

Usa los tokens y componentes de cada marca (marca/*/assets) y de redes (redes/sistema/redes.css).
Fotos: pares originales/mejoradas de la carpeta Nestor del usuario (permiso del 19/10), copiados en redes/insumos/fotos/.
Sin precios, @, dominios ni WhatsApp: ML desenfoca o modera esas fotos (D-60). Las portadas van sin texto ni logo
(ML marca text_logo en la foto principal).
"""
import pathlib

AQUI = pathlib.Path(__file__).resolve().parent
M = "../../../marca"
R = "../../../redes"
F = f"{R}/insumos/fotos"


def pagina(nombre, marca, tema, cuerpo, extra_css=""):
    tok = f"{M}/restauracion-de-fotos/assets" if marca == "rf" else f"{M}/tu-cancion/assets"
    html = f"""<!doctype html>
<!-- Foto para Mercado Libre (1080x1080, se exporta a 1200x1200). Generada por generar.py: no se edita a mano. -->
<html lang="es"><head><meta charset="utf-8"><meta name="lienzo" content="1080x1080"><title>{nombre}</title>
<link rel="stylesheet" href="{tok}/design-tokens.css">
<link rel="stylesheet" href="{tok}/componentes.css">
<link rel="stylesheet" href="{R}/sistema/redes.css">
<style>body{{margin:0}} {extra_css}</style></head>
<body><main class="r-lienzo r-lienzo--cuadrado" data-marca="{marca}" data-theme="{tema}">
{cuerpo}
</main></body></html>
"""
    (AQUI / f"{nombre}.html").write_text(html, encoding="utf-8")


def comp(par, prop, tags=True, estilo=""):
    t = ('<span class="r-comparador__tag r-comparador__tag--antes">Antes</span>'
         '<span class="r-comparador__tag r-comparador__tag--despues">Después</span>') if tags else ""
    return (f'<div class="r-comparador" style="--r-proporcion:{prop};{estilo}">'
            f'<img src="{F}/{par}-antes.jpg" alt="La foto original">'
            f'<img class="r-comparador__despues" src="{F}/{par}-despues.jpg" alt="La misma foto restaurada">'
            f'<span class="r-comparador__linea"></span>{t}</div>')


def dos_fotos(par):
    return ('<div class="rf-antes-despues dos">'
            f'<figure class="rf-foto rf-foto--antes"><img src="{F}/{par}-antes.jpg" alt="La foto original">'
            '<span class="rf-tag">Antes</span></figure>'
            f'<figure class="rf-foto rf-foto--despues"><img src="{F}/{par}-despues.jpg" alt="La misma foto restaurada">'
            '<span class="rf-tag rf-tag--despues">Después</span></figure></div>')


LOGO_RF_CINTA = (f'<div class="r-cabecera"><img class="r-logo" src="{M}/restauracion-de-fotos/assets/logos/'
                 'rf-logo-yema.svg" alt="Restauración de fotos"></div>')
LOGO_RF = (f'<div class="r-cabecera"><img class="r-logo" src="{M}/restauracion-de-fotos/assets/logos/rf-logo.svg" '
           'alt="Restauración de fotos"></div>')
LOGO_TC_B = (f'<div class="r-cabecera"><img class="r-logo" src="{M}/tu-cancion/assets/logos/tc-logo-blanco.svg" '
             'alt="Tu Canción"></div>')
LOGO_TC = f'<div class="r-cabecera"><img class="r-logo" src="{M}/tu-cancion/assets/logos/tc-logo.svg" alt="Tu Canción"></div>'
LLENO = ".r-lienzo{padding:0} .r-comparador::before,.r-comparador::after{display:none} .r-comparador{border-radius:0}"
DOS = (".dos{display:grid;grid-template-columns:1fr 1fr;height:560px} .dos figure{margin:0;height:560px} "
       ".dos img{width:100%;height:100%;object-fit:cover;display:block}")
NOTA = ".nota{margin:0;font-size:38px;line-height:1.25}"

DISCO = ('<svg class="tc-funda__disco" viewBox="2 20 96 96" aria-hidden="true">'
         '<circle class="tc-disco__vin" cx="50" cy="68" r="48"/>'
         '<path class="tc-disco__brillo" d="M62.89 37.62A33 33 0 0 1 77.68 50.03"/>'
         '<path class="tc-disco__brillo" d="M37.11 98.38A33 33 0 0 1 22.32 85.97"/>'
         '<circle class="tc-disco__surco" cx="50" cy="68" r="40"/><circle class="tc-disco__surco" cx="50" cy="68" r="33"/>'
         '<circle class="tc-disco__surco" cx="50" cy="68" r="26"/><circle class="tc-disco__etq" cx="50" cy="68" r="17"/>'
         '<path class="tc-disco__marca" d="M40.91 62.75A10.5 10.5 0 0 1 59.09 62.75"/>'
         '<circle class="tc-disco__punto" cx="50" cy="78.5" r="1.7"/><circle class="tc-disco__hueco" cx="50" cy="68" r="3.6"/></svg>')


def funda(a, b):
    return (f'<div class="tc-con-disco">{DISCO}<div class="tc-funda tc-funda--chica"><div class="tc-funda__cabecera">'
            '<span class="tc-tag">Lado A</span><span class="tc-funda__duracion">3:12</span></div>'
            f'<div class="tc-funda__mano"><span class="tc-funda__renglon">{a}</span>'
            f'<span class="tc-funda__renglon">{b}</span></div></div></div>')


def pasos(*items):
    return '<ol class="r-pasos">' + "".join(f"<li>{x}</li>" for x in items) + "</ol>"


def main():
    # ---- Restauración: portadas sin texto ni logo ----
    pagina("rf-portada-foto", "rf", "cinta", comp("nestor-familia-playa", "1 / 1", tags=False, estilo="width:1080px"), LLENO)
    grilla = "".join(comp(p, "1 / 1", tags=False) for p in
                     ("nestor-playa-pelota", "nestor-futbol", "nestor-montana", "nestor-familia-playa"))
    pagina("rf-portada-pack", "rf", "cinta", f'<div class="mosaico">{grilla}</div>',
           LLENO + " .mosaico{display:grid;grid-template-columns:1fr 1fr;gap:12px;width:1080px;height:1080px}"
                   " .mosaico .r-comparador{width:534px}")
    # ---- Restauración: secundarias ----
    pagina("rf-como-nueva", "rf", "cinta", LOGO_RF_CINTA + '<h1 class="r-titulo">Esa foto de siempre, como nueva.</h1>'
           + comp("nestor-lago", "16 / 9") + '<p class="nota">Sacamos manchas, roturas, rayones y dobleces.</p>',
           ".r-titulo{font-size:80px} " + NOTA)
    pagina("rf-pasos", "rf", "etiqueta", LOGO_RF + '<h1 class="r-titulo">Así se pide</h1>' + pasos(
        "Comprás y nos mandás la foto por la mensajería de Mercado Libre.",
        "En menos de 2 horas te mostramos la vista previa.",
        "Tenés una corrección incluida.",
        "Recibís el archivo en alta resolución."), ".r-pasos{gap:52px} .r-pasos li{font-size:46px}")
    pagina("rf-color", "rf", "yema", LOGO_RF + '<h1 class="r-titulo">¿En blanco y negro? La pasamos a color.</h1>'
           + dos_fotos("nestor-bebe-byn") + '<p class="nota">O la dejás con colores de época o en blanco y negro: vos elegís.</p>',
           ".r-titulo{font-size:72px} " + DOS + " " + NOTA)
    pagina("rf-caras", "rf", "cinta", LOGO_RF_CINTA + '<h1 class="r-titulo">La abuela sigue siendo la abuela.</h1>'
           + dos_fotos("nestor-abuela")
           + '<p class="nota">No inventamos caras: si alguien no queda igual, lo corregimos mirando tu original.</p>',
           ".r-titulo{font-size:72px} " + DOS + " .dos img{object-position:50% 30%} " + NOTA)
    despues = "".join(f'<img src="{F}/{p}-despues.jpg" alt="">' for p in (
        "nestor-futbol", "nestor-montana", "nestor-playa-pelota", "nestor-guitarras", "nestor-cascada", "nestor-familia-playa"))
    pagina("rf-album", "rf", "etiqueta", LOGO_RF + '<h1 class="r-titulo">Todo el álbum familiar, restaurado.</h1>'
           f'<div class="album">{despues}</div>'
           '<p class="nota">Packs de 5, 10 o 20 fotos, en alta resolución para imprimir.</p>',
           ".r-titulo{font-size:80px} .album{display:grid;grid-template-columns:repeat(3,1fr);gap:14px} "
           ".album img{width:100%;height:262px;object-fit:cover;border-radius:var(--r-radio-sm);display:block} " + NOTA)
    for nombre, linea in (("rf-cuadro-enmarcado", "Restauración, impresión, marco con vidrio y envío a tu casa."),
                          ("rf-cuadro-ecocuero", "Restauración, impresión en ecocuero sobre bastidor de madera "
                                                 "y envío a tu casa.")):
        pagina(nombre, "rf", "cinta", LOGO_RF_CINTA + '<h1 class="r-titulo">Primero la restauramos. Después, a la pared.</h1>'
               + comp("nestor-cascada", "16 / 9") + f'<p class="nota">{linea}</p>', ".r-titulo{font-size:76px} " + NOTA)

    # ---- Tu Canción ----
    escena = (".r-lienzo{padding:0} .escena{position:relative;width:1080px;height:1080px} "
              ".escena .tc-con-disco{position:absolute;right:36px;top:50%;transform:translateY(-50%) scale(.8);"
              "transform-origin:right center}")
    pagina("tc-portada-cancion", "tc", "birome",
           f'<div class="escena"><img class="foto" src="{F}/nestor-abuelo-guitarra-despues.jpg" alt="Un abuelo tocando la '
           f'guitarra">{funda("Para", "el abuelo")}</div>',
           escena + " .foto{position:absolute;left:0;top:0;width:620px;height:1080px;object-fit:cover}")
    tira = "".join(f'<img src="{F}/{p}-despues.jpg" alt="">' for p in
                   ("nestor-torta-byn", "nestor-abuelo-guitarra", "nestor-bebe-byn"))
    pagina("tc-portada-combo", "tc", "birome", f'<div class="escena"><div class="tira">{tira}</div>'
           f'{funda("Para", "la familia")}</div>',
           escena + " .tira{position:absolute;left:0;top:0;bottom:0;width:560px;display:grid;"
                    "grid-template-rows:repeat(3,1fr);gap:10px} .tira img{width:100%;height:100%;object-fit:cover;display:block}")
    pagina("tc-pasos", "tc", "papel", LOGO_TC + '<h1 class="r-titulo">Así se pide</h1>' + pasos(
        "Nos contás su historia por la mensajería de Mercado Libre.",
        "En menos de 48 horas escuchás la primera versión.",
        "Hasta 5 cambios incluidos, en la letra o el estilo.",
        "Recibís el MP3 final en alta calidad."), ".r-pasos{gap:52px} .r-pasos li{font-size:46px}")
    pagina("tc-pasos-combo", "tc", "papel", LOGO_TC + '<h1 class="r-titulo">Su canción y sus fotos, en un video</h1>' + pasos(
        "Nos contás su historia y nos mandás hasta 20 fotos.",
        "Restauramos 3 de esas fotos.",
        "Hasta 5 cambios incluidos en la canción.",
        "En hasta 72 horas tenés el video con su canción de fondo."),
        ".r-titulo{font-size:80px} .r-pasos{gap:44px} .r-pasos li{font-size:44px}")
    pagina("tc-recibis", "tc", "birome", LOGO_TC_B + '<h1 class="r-titulo">Una canción que solo esa persona puede recibir.</h1>'
           '<ul class="lista"><li>Letra escrita con sus recuerdos, apodos y lugares.</li>'
           '<li>Su nombre bien pronunciado.</li><li>De 2 a 4 minutos, en el género que elijas.</li>'
           '<li>Hecha con IA y revisada por una persona.</li></ul>',
           ".r-titulo{font-size:80px} .lista{margin:0;padding-left:44px;display:flex;flex-direction:column;gap:40px;"
           "font-size:46px;line-height:1.25} .lista li::marker{color:var(--accent)}")
    print("\n".join(sorted(p.name for p in AQUI.glob("*.html"))))


if __name__ == "__main__":
    main()
