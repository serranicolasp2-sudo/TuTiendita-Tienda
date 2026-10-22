"""Restauración de fotos: análisis previo, referencias de color, instrucción para Codex y control de los cambios.

Por cada foto del cliente:
  1. analizar()      Codex mira la foto y busca en internet: tipo de toma, plano, angulación, soporte, época,
                     daños y objetos con colores verificables (personajes, marcas, envases, uniformes, autos…).
                     Queda en <pedido>\\0-analisis\\<foto>.json.
  2. referencias()   cruza esos objetos con produccion\\referencias\\biblioteca.json (colores verificados).
                     A Codex le llegan solo los colores en texto: con la imagen de referencia adjunta copia su
                     dibujo (prueba del 09/10: Daisy cambió de pose y perdió la torta que tenía en la mano).
  3. instruccion()   arma el prompt: lo que no se toca, lo que se arregla, los colores de referencia, los datos
                     del cliente y, si es un cambio, el pedido del cliente ya validado.
  4. validar_cambio() antes de rehacer, Codex decide si el comentario del cliente tiene sentido y qué parte se hace.

Registro: cada objeto con colores se suma a produccion\\referencias\\registro.jsonl y registro.md
(objeto, época, colores, fuente). No se guardan datos de las personas.
"""
import datetime
import json
import pathlib
import re
import tempfile
import threading

from PIL import Image

from codexcli import correr_json, objeto

REFERENCIAS = pathlib.Path(__file__).resolve().parents[2] / "produccion" / "referencias"
BIBLIOTECA = REFERENCIAS / "biblioteca.json"
REGISTRO = REFERENCIAS / "registro.jsonl"
REGISTRO_MD = REFERENCIAS / "registro.md"

TEXTO = {"type": "string"}
LISTA_TEXTO = {"type": "array", "items": TEXTO}


def suelto(texto: str) -> str:
    """Para intercalar un dato de la ficha en una frase: sin mayúscula inicial ni punto final."""
    texto = (texto or "").strip().rstrip(".")
    return texto[:1].lower() + texto[1:]


def opciones(*valores):
    return {"type": "string", "enum": list(valores)}


ESQUEMA_FICHA = objeto({
    "tipo": TEXTO, "plano": TEXTO, "angulacion": TEXTO,
    "orientacion": opciones("vertical", "horizontal", "cuadrada"),
    "soporte": TEXTO,
    "estado_color": opciones("blanco y negro", "sepia", "color desteñido", "color", "coloreada a mano"),
    "iluminacion": TEXTO, "epoca": TEXTO, "indicios_epoca": LISTA_TEXTO, "contexto": TEXTO,
    "danos": {"type": "array", "items": objeto({"tipo": TEXTO, "zona": TEXTO,
                                                "gravedad": opciones("leve", "media", "grave")})},
    "caras": objeto({"cantidad": {"type": "integer"}, "estado": TEXTO}),
    "elementos": {"type": "array", "items": objeto({"objeto": TEXTO, "ubicacion": TEXTO, "colores": TEXTO,
                                                    "fuente": TEXTO,
                                                    "confianza": opciones("alta", "media", "baja")})},
    "paleta": TEXTO, "instrucciones": LISTA_TEXTO, "apta": {"type": "boolean"}, "motivo": TEXTO,
})

ESQUEMA_CAMBIO = objeto({
    "valida": {"type": "boolean"},
    "categoria": opciones("color", "daño", "fidelidad", "nitidez", "encuadre", "blanco_y_negro", "cara",
                          "agregar_quitar", "sin_sentido", "otra"),
    "instruccion": TEXTO, "fotos": LISTA_TEXTO, "rechazado": TEXTO, "mensaje_cliente": TEXTO,
    "modo_color": opciones("", "Color", "Mantener colores de época", "Blanco y negro"),
})


# ---------------- biblioteca y registro ----------------
def biblioteca() -> list:
    try:
        return json.loads(BIBLIOTECA.read_text(encoding="utf-8"))["referencias"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return []


def referencias(ficha: dict | None) -> list:
    """Entradas de la biblioteca cuyo nombre aparece entre los objetos detectados."""
    if not ficha:
        return []
    texto = " ".join(f"{e['objeto']} {e['ubicacion']}" for e in ficha["elementos"]).lower()
    return [r for r in biblioteca() if any(n in texto for n in r["nombres"])]


_registro = threading.Lock()


def registrar(ficha: dict, pid: str):
    """Suma los objetos con colores al registro general (sin datos de personas)."""
    with _registro:
        _registrar(ficha, pid)


def _registrar(ficha: dict, pid: str):
    fecha = datetime.date.today().isoformat()
    with REGISTRO.open("a", encoding="utf-8") as f:
        for e in ficha["elementos"]:
            f.write(json.dumps({"fecha": fecha, "pedido": pid, "epoca": ficha["epoca"], "objeto": e["objeto"],
                                "colores": e["colores"], "fuente": e["fuente"], "confianza": e["confianza"]},
                               ensure_ascii=False) + "\n")
    filas = [json.loads(l) for l in REGISTRO.read_text(encoding="utf-8").splitlines() if l.strip()]
    tabla = "\n".join(f"| {r['fecha']} | {r['pedido']} | {r['epoca']} | {r['objeto']} | {r['colores']} | "
                      f"{r['fuente']} | {r['confianza']} |".replace("\n", " ") for r in reversed(filas))
    REGISTRO_MD.write_text(
        "# Registro de referencias de color\n\nLo arma el bot con cada foto analizada (lo más nuevo arriba). "
        "Si una referencia es buena y se repite, pasala a biblioteca.json con su imagen.\n\n"
        "| Fecha | Pedido | Época | Objeto | Colores | Fuente | Confianza |\n|---|---|---|---|---|---|---|\n"
        + tabla + "\n", encoding="utf-8")


# ---------------- 1. análisis ----------------
def prompt_analisis(datos: dict) -> str:
    color = datos.get("color") or ""
    conocidas = "\n".join(f"- {r['colores']}" for r in biblioteca()) or "- (ninguna todavía)"
    return f"""Sos restaurador fotográfico y documentalista. Te paso la foto de un cliente que vamos a restaurar. NO la edites ni generes imágenes: solo analizala y devolvé la ficha con el formato JSON pedido.
La primera imagen es la foto completa. Las cuatro siguientes son recortes ampliados de la MISMA foto (arriba a la izquierda, arriba a la derecha, abajo a la izquierda y abajo a la derecha, con partes repetidas): usalos para ver los detalles chicos. Recorrelos uno por uno antes de responder y no cuentes dos veces lo que aparece en dos recortes.

1. La toma: tipo (retrato, grupo, evento, paisaje, carnet, foto de estudio…), plano (general, entero, americano, medio, primer plano, detalle), angulación (normal, picado, contrapicado, cenital), orientación, soporte (copia de papel con borde, Polaroid, diapositiva, foto de estudio, recorte…), estado del color e iluminación (flash directo, luz natural, interior con lámpara…).
2. La época: rango de años probable y los indicios (ropa, peinados de los adultos, objetos, autos, envases, tipo de papel y de borde). Cruzá varios indicios: no dates por uno solo. Contexto probable (ocasión y lugar). Asumí Argentina salvo que la foto indique otra cosa.
3. Los daños: tipo, zona y gravedad.
4. Las caras: cuántas hay y en qué estado. NO identifiques a nadie ni adivines nombres. Si una cara principal está destruida (no se puede reconstruir sin inventar rasgos), poné apta=false y explicá el motivo; si no, apta=true y motivo vacío.
5. Objetos con colores verificables: personajes de dibujos o historietas, marcas y envases (gaseosas, golosinas, cigarrillos), carteles, juguetes, guardapolvos y uniformes, camisetas de fútbol, banderas, autos, electrodomésticos, etc. Un elemento por objeto: si hay dos carteles con personajes distintos, son dos elementos (identificá cada personaje). Leé los textos y etiquetas visibles en los envases para saber la marca. Para cada uno BUSCÁ EN INTERNET cómo eran sus colores reales en esa época y anotá colores concretos (con código hex si podés) y la URL de la fuente. Si no encontrás fuente, poné colores plausibles para la época, fuente vacía y confianza baja. (Aunque el cliente la quiera en blanco y negro: puede cambiar de idea en la revisión.)
6. Paleta general: colores típicos de la época para paredes, muebles, ropa y vajilla sin referencia.
7. Instrucciones: de 3 a 8 líneas concretas SOLO de reparación (qué daño arreglar y dónde, contraste, zonas perdidas, personas u objetos fuera de foco que tienen que seguir igual). NO hables de colores ni pidas colorear: los colores van en los objetos y en la paleta, y el modo de color lo decide el cliente. Nunca pidas cambiar caras, encuadre o cantidad de personas, ni agregar o sacar cosas.

Referencias que ya tenemos verificadas (si aparece el objeto, usalas tal cual):
{conocidas}

Lo que pidió el cliente: color = {color or "mantener"}; comentarios = {datos.get("comentarios") or "ninguno"}.
No ejecutes comandos."""


def recortes(foto: pathlib.Path, carpeta: pathlib.Path) -> list:
    """Cuatro cuadrantes ampliados (con solapamiento): sin esto, Codex no ve los objetos chicos (carteles, etiquetas)."""
    im = Image.open(foto).convert("RGB")
    w, h = im.size
    ancho, alto = int(w * 0.6), int(h * 0.6)
    salida = []
    for i, (x, y) in enumerate(((0, 0), (w - ancho, 0), (0, h - alto), (w - ancho, h - alto)), 1):
        c = im.crop((x, y, x + ancho, y + alto))
        escala = 1600 / max(c.size)
        if escala > 1:
            c = c.resize((round(c.width * escala), round(c.height * escala)), Image.LANCZOS)
        ruta = carpeta / f"recorte-{i}.jpg"
        c.save(ruta, quality=92)
        salida.append(ruta)
    return salida


def analizar(foto: pathlib.Path, datos: dict) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        return correr_json(prompt_analisis(datos), ESQUEMA_FICHA, fotos=[foto, *recortes(foto, pathlib.Path(tmp))],
                           buscar=True, timeout=900)


# ---------------- 2 y 3. instrucción para Codex ----------------
def usa_colores(datos: dict, ficha: dict | None) -> bool:
    """"A color" y "Mantener colores de época" llevan color (vivo o de época); "En blanco y negro", no."""
    return (datos.get("color") or "") != "Blanco y negro"


MONOCROMA = ("blanco y negro", "sepia")
COLOREAR = re.compile(r"colore|colorid|\b(rojo|roja|azul|verde|amarill|naranja|rosa|celeste|violeta|bordó|"
                      r"marr[oó]n|dorad|plateado)", re.I)


def parte_color(datos: dict, ficha: dict | None) -> str:
    """Definición de los modos del usuario (13/10): "A color" = vivo, actual y limpio; "Mantener colores de época" =
    paleta reducida de la época con la gestión de color de las copias de entonces (tonos sepia/cálidos visibles);
    "En blanco y negro" = grises neutros."""
    color = datos.get("color") or ""
    epoca = f"de esa época ({suelto(ficha['epoca'])})" if ficha else "de esa época"
    monocroma = bool(ficha) and ficha["estado_color"] in MONOCROMA + ("coloreada a mano",)
    if color == "Blanco y negro":
        return ("Pasala a BLANCO Y NEGRO NEUTRO: escala de grises pura, sin tono sepia ni ningún color en ninguna "
                "parte (tampoco en carteles, envases ni etiquetas). Recuperá el contraste y el rango de grises: "
                "negros profundos y blancos limpios, sin quemar las caras.")
    if color == "Color":
        return (("Coloreala" if monocroma else "Devolvele el color") + " A COLOR VIVO Y ACTUAL: colores vivos, limpios "
                "y naturales, como una foto sacada hoy con una buena cámara. Blancos neutros, sin dominantes, sin tono "
                "sepia ni desteñido, saturación plena pero creíble. Pieles naturales y distintas para cada persona. "
                "Los objetos con referencia llevan exactamente esos colores.")
    return (("Coloreala" if monocroma else "Restaurá su color") + f" con los COLORES DE ÉPOCA de las fotos {epoca}: "
            "una paleta REDUCIDA, de pocos colores, apagados y terrosos, con la gestión de color de las copias de "
            "entonces: una dominante cálida tirando a sepia bien visible, blancos cremosos, negros amarronados y "
            "saturación baja. Tiene que notarse que es una foto de aquella época, no una foto actual. Los objetos con "
            "referencia llevan sus colores, pero apagados dentro de esa paleta.")


def colores_referencia(datos: dict, ficha: dict | None, refs: list) -> list:
    """Bloques del prompt con los colores investigados (vacío en blanco y negro o sin análisis)."""
    if not (usa_colores(datos, ficha) and ficha):
        return []
    lineas = [f"- {r['colores']}" for r in refs]
    for e in ficha["elementos"]:
        if e["colores"] and not any(n in e["objeto"].lower() for r in refs for n in r["nombres"]):
            lineas.append(f"- {e['objeto']} ({suelto(e['ubicacion'])}): {e['colores']}")
    bloques = ["COLORES DE REFERENCIA (investigados para esta foto):\n" + "\n".join(lineas)] if lineas else []
    if ficha["paleta"] and (datos.get("color") or "") != "Color":
        bloques.append(f"Para lo demás, paleta de la época: {ficha['paleta']}")
    return bloques


FINAL = ("Generá exactamente UNA imagen. No ejecutes comandos ni intentes guardar archivos. "
         "Cuando esté generada, respondé solo OK.")


def instruccion_cambio(datos: dict, ficha: dict | None, refs: list, cambio: str, modo_nuevo: str | None = None) -> str:
    """Un cambio se aplica SOBRE la versión que el cliente ya vio: lo que no pidió cambiar ya está aprobado y no
    se tiene que mover (si se rehace desde el original, Codex reinterpreta todo de nuevo)."""
    partes = ["Editá esta foto con tu herramienta de generación de imágenes. La PRIMERA imagen es la versión "
              "restaurada que el cliente ya revisó: es la base, y todo lo que no esté en el cambio pedido ya está "
              "aprobado. La SEGUNDA imagen es la foto original escaneada: usala solo para comparar cómo eran de verdad "
              "las caras y los objetos; no copies sus daños, manchas ni su color.",
              f"CAMBIO PEDIDO (es lo ÚNICO que se modifica, y TIENE QUE VERSE CLARAMENTE en el resultado: si la zona "
              f"queda casi igual, está mal): {cambio}"]
    if modo_nuevo:
        nuevos = {**datos, "color": modo_nuevo}
        partes += ["El cambio incluye el modo de color. " + parte_color(nuevos, ficha), *colores_referencia(nuevos, ficha, refs)]
    partes.append("TODO LO DEMÁS QUEDA IDÉNTICO A LA PRIMERA IMAGEN: mismas caras y expresiones, mismos colores, luz, "
                  "encuadre, fondo, objetos, nitidez y grano. No mejores, no limpies, no recolorees ni retoques nada que "
                  "no esté en el cambio pedido: si el cambio es en una zona, el resto de la foto no se mueve.")
    partes.append("Siguen valiendo estas reglas: no cambies rasgos ni expresiones de ninguna cara (salvo para hacerla "
                  "más fiel a la original, si eso es lo pedido), no agregues ni saques personas u objetos y no cambies "
                  "el encuadre.")
    partes.append(FINAL)
    return "\n\n".join(partes)


def instruccion(datos: dict, ficha: dict | None, refs: list, cambio: str | None = None) -> str:
    partes = ["Restaurá esta fotografía con tu herramienta de generación de imágenes. La imagen adjunta es la "
              "foto del cliente y es la única base."]
    orient = f" ({suelto(ficha['orientacion'])})" if ficha else ""
    luz = f" ({suelto(ficha['iluminacion'])})" if ficha else ""
    partes.append(
        "QUÉ NO SE TOCA (prioridad máxima):\n"
        "1. Las caras: misma forma de ojos, nariz, boca, cejas, orejas, mandíbula, arrugas, lunares, peinado, edad y "
        "expresión. No rejuvenezcas, no embellezcas, no maquilles, no corrijas dientes ni mirada. Si una parte de "
        "una cara está dañada, no inventes rasgos: dejala suave y apenas definida antes que crear algo que no se ve.\n"
        f"2. El encuadre y la proporción{orient}, la pose, la ropa, el fondo y la cantidad de personas y objetos. "
        "No agregues ni saques nada. Los dibujos, carteles, envases y estampados conservan exactamente su forma, su "
        "pose y lo que tienen en la mano: a un personaje solo se le pone color, no se lo redibuja.\n"
        + (f"3. La luz original{luz}, las sombras y la textura de una fotografía real: colores actuales sí, pero que "
           "siga siendo esta foto (no una pintura, ni un render, ni un retrato de estudio).\n"
           if (datos.get("color") or "") == "Color" else
           f"3. La luz original{luz}, las sombras y el grano de una foto de su época: que no parezca una imagen "
           "digital moderna, ni una pintura, ni un retrato de estudio.\n") +
        "4. Lo que está fuera de foco o movido (personas del fondo, caras chicas o borrosas) queda igual de suave: "
        "no lo redefinas ni le inventes rasgos. Cada persona sigue siendo la misma: mismo sexo, edad, peinado y ropa.")
    danos = [f"- {d['tipo']}: {suelto(d['zona'])}" for d in (ficha or {}).get("danos", [])]
    partes.append("QUÉ SE ARREGLA:\n" + "\n".join(danos or ["- rayas, dobleces, manchas, polvo, roturas, hongos y zonas descoloridas"])
                  + "\n- Si una parte está perdida y no se puede deducir con certeza, reconstruila de la forma más "
                  "simple y neutra posible.")
    partes.append("COLOR: " + parte_color(datos, ficha))
    if usa_colores(datos, ficha):
        partes.append("PIEL: toda la piel visible (cara, cuello, escote o pecho, brazos, manos, piernas) lleva color piel "
                      "natural, el mismo en toda la persona. No la confundas con ropa: si en la original una zona del cuerpo "
                      "tiene el mismo brillo que la cara, es piel y no puede quedar oscura (13/10: un pecho con vello quedó "
                      "como un suéter marrón casi negro).")
    partes += colores_referencia(datos, ficha, refs)
    notas = [i for i in (ficha or {}).get("instrucciones", [])
             if usa_colores(datos, ficha) or not COLOREAR.search(i)]   # en modos sin color, nada que pida colorear
    if notas:
        partes.append("NOTAS DEL ANÁLISIS:\n" + "\n".join(f"- {i}" for i in notas))
    if datos.get("comentarios"):
        partes.append(f"DATOS DEL CLIENTE (respetalos si no contradicen 'Qué no se toca'): {datos['comentarios']}")
    if cambio:
        partes.append(f"CAMBIO PEDIDO POR EL CLIENTE después de ver una versión anterior: {cambio}\n"
                      "Aplicalo partiendo de esta foto original y mantené todo lo demás según estas reglas.")
    partes.append("Generá exactamente UNA imagen. No ejecutes comandos ni intentes guardar archivos. "
                  "Cuando esté generada, respondé solo OK.")
    return "\n\n".join(partes)


# ---------------- 4. pedidos de cambio ----------------
def prompt_cambio(nota: str, datos: dict, nombres: list, con_fotos: bool, con_previas: bool = False) -> str:
    adjuntos = ""
    if con_fotos and con_previas:
        adjuntos = (" Te adjunto, en ese mismo orden, cada ORIGINAL escaneada seguida de la VERSIÓN RESTAURADA que vio el "
                    "cliente (original 1, versión 1, original 2, versión 2…). Comparalas para entender qué está mal.")
    elif con_fotos:
        adjuntos = " Te adjunto los originales en ese mismo orden."
    return f"""Sos el control de calidad de un servicio de restauración de fotos antiguas. El cliente vio la vista previa y escribió este pedido de cambio:
\"\"\"{nota}\"\"\"

Fotos del pedido (nombres de archivo, en este orden): {", ".join(nombres)}.{adjuntos}
Lo que pidió al comprar: color = {datos.get("color") or "mantener"}; comentarios = {datos.get("comentarios") or "ninguno"}.

Se PUEDE: corregir colores (ropa, piel, pelo, objetos, cielo, tono general), sacar más daño (manchas, rayas, roturas), más o menos nitidez, ser más fiel al original (por ejemplo "la cara de mi abuela quedó distinta" es válido: hay que respetar más la original), pasar a blanco y negro o a color, recortar o enderezar.
NO se puede: cambiar rasgos o expresión de una cara (hacer sonreír, adelgazar, rejuvenecer, abrir los ojos), agregar o sacar personas u objetos, cambiar el fondo o la ropa por otra, ni nada sin relación con la foto.

Decidí:
- valida: true si al menos una parte se puede hacer. false si el texto no tiene sentido (letras al azar, una prueba, insultos, algo sin relación con la foto) o si todo lo pedido está fuera de las reglas.
- categoria: la principal.
- modo_color: si pide pasar la foto a color, dejarla con su color original o pasarla a blanco y negro, el modo nuevo ("Color", "Mantener colores de época" o "Blanco y negro"); vacío si no cambia el modo.
- instruccion: SOLO la parte que se hace, reescrita como orden clara y CONCRETA para el restaurador (español, imperativo). Tiene que decir: qué zona (ubicada con referencias visibles: "el pecho, dentro del cuello en V del abrigo blanco, debajo de las antiparras"), qué hay ahí en la foto original (piel, tela, pared…, y si es clara u oscura), qué está mal en la versión y cómo tiene que quedar (color y brillo concretos). Nada de aclaraciones que contradigan el pedido (si pide aclarar algo, no agregues "respetando los colores originales"). Vacío si no es válida.
  · Mirá bien qué ES la zona en la original. Si el cliente dice que una parte del cuerpo (pecho, escote, cuello, brazos, manos, piernas) "salió negra" u "oscura", casi siempre esa zona es PIEL que se coloreó como si fuera ropa: decilo así ("es piel, no una prenda") y pedí que tenga el mismo color piel que la cara.
  · Para el color de destino usá una referencia de la misma foto siempre que puedas ("del mismo color piel que la cara", "del mismo blanco que el abrigo").
  · Si sobre la zona hay algo que no se toca (anteojos, antiparras, collar, botones, un objeto en la mano), nombralo y pedí que quede igual.
- fotos: nombres de archivo a los que se refiere; lista vacía si es para todas o no se puede saber.
- rechazado: qué parte no se hace y por qué. Vacío si se hace todo.
- mensaje_cliente: mensaje corto y amable para mandarle por WhatsApp (voseo argentino, en plural como equipo, sin tecnicismos, máximo 350 caracteres). Si se hace una parte: contale que ya la estamos aplicando y explicá por qué el resto no se puede. Si no es válida: explicá o pedile que aclare qué quiere cambiar. Vacío si se hace todo.
No ejecutes comandos."""


CUERPO = re.compile(r"\b(pecho|escote|cuello|brazos?|manos?|piernas?|panza|hombros?|espalda|piel|cara|frente|"
                    r"mejillas?|rodillas?|pies)\b", re.I)
ROPA = re.compile(r"\b(remera|camisa|saco|suéter|sueter|buzo|vestido|pollera|pantal[oó]n|campera|abrigo|tela|ropa|"
                  r"corbata|chaleco|pulóver|pulover|blusa)\b", re.I)
OSCURO = re.compile(r"negr|oscur|marr[oó]n|sucio|manchad|gris", re.I)


def pista_de_piel(nota: str) -> str:
    """Si el cliente nombra una parte del cuerpo (no una prenda) y dice que salió oscura, es piel coloreada como ropa
    (13/10, RF-0010: "el pecho quedó negro"; el validador lo llamaba "tela oscura" y Codex lo dejaba igual)."""
    if CUERPO.search(nota) and OSCURO.search(nota) and not ROPA.search(nota):
        return ("\n\nIMPORTANTE: el cliente habla de una parte del cuerpo. Esa zona es PIEL, aunque en la versión parezca "
                "una prenda: no la llames tela ni ropa. La instrucción tiene que pedir que sea piel del mismo color que la "
                "cara (con vello o textura si se ve en la original), sin tocar lo que haya encima.")
    return ""


def validar_cambio(nota: str, datos: dict, originales: list, previas: list | None = None) -> dict:
    """previas: la versión que vio el cliente de cada original (mismo orden); sin ella, Codex no ve qué está mal."""
    con_previas = bool(previas) and len(previas) == len(originales) and len(originales) <= 4
    con_fotos = len(originales) <= 6
    fotos = [x for par in zip(originales, previas) for x in par] if con_previas else (originales if con_fotos else [])
    prompt = prompt_cambio(nota, datos, [f.name for f in originales], con_fotos, con_previas) + pista_de_piel(nota)
    return correr_json(prompt, ESQUEMA_CAMBIO, fotos=fotos, timeout=600)


ESQUEMA_VERIFICACION = objeto({"aplicado": {"type": "boolean"}, "motivo": TEXTO})


def verificar_cambio(antes: pathlib.Path, despues: pathlib.Path, instruccion: str) -> dict:
    """¿Se ve el cambio pedido? Si Codex devolvió casi la misma foto, no se manda al cliente."""
    prompt = f"""Sos el control de calidad de un servicio de restauración de fotos. Te adjunto dos imágenes: la PRIMERA es la versión anterior y la SEGUNDA es la nueva, que tenía que aplicar este cambio:
\"\"\"{instruccion}\"\"\"
Compará la zona del cambio en las dos. aplicado = true solo si el cambio se ve claramente en la segunda (no alcanza con una diferencia mínima). motivo: en una frase, qué ves en esa zona en la segunda imagen. No ejecutes comandos."""
    return correr_json(prompt, ESQUEMA_VERIFICACION, fotos=[antes, despues], timeout=300)


def fotos_del_cambio(v: dict, originales: list) -> set | None:
    """Stems de las fotos a rehacer; None = todas."""
    pedidas = {pathlib.Path(n).stem.lower() for n in v.get("fotos") or []}
    elegidas = {f.stem for f in originales if f.stem.lower() in pedidas}
    return elegidas or None
