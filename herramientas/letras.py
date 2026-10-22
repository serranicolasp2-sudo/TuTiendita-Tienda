"""Letras de Tu Canción: Codex escribe la letra y el estilo para Suno; una segunda IA (Claude con tu suscripción o, si
no está disponible, Codex de nuevo) la revisa contra lo que contó el cliente y corrige; y en un cambio se toca SOLO
lo que el cliente pidió.

13/10 (TC-0002): el cliente pidió "está buena la letra pero quiero que suene como One de Metallica" y se reescribió
toda la letra. Ahora primero se decide qué cambia (letra, estilo, título) y lo que no se pidió se copia tal cual.
"""
import json
import logging
import pathlib
import re

import claudecli
from codexcli import correr_json, objeto

log = logging.getLogger("bot")
PLANTILLA = pathlib.Path(__file__).resolve().parents[2] / "produccion" / "prompts" / "letra-cancion.md"
TEXTO = {"type": "string"}
SI_NO = {"type": "boolean"}
CAMPOS = ("titulo", "letra", "estilo", "excluir", "foneticas")
ESQUEMA_VERSION = objeto({c: TEXTO for c in CAMPOS})
ESQUEMA_REVISION = objeto({"problemas": {"type": "array", "items": TEXTO}, "observaciones": {"type": "array", "items": TEXTO},
                           **{c: TEXTO for c in CAMPOS}})
ESQUEMA_CAMBIO = objeto({"cambia_letra": SI_NO, "cambia_estilo": SI_NO, "cambia_titulo": SI_NO,
                         "instruccion_letra": TEXTO, "instruccion_estilo": TEXTO, "resumen": TEXTO})
ETIQUETAS = {"para_quien": "Para quién es (nombre y apodo)", "vinculo": "Qué es para quien regala",
             "ocasion": "Ocasión", "estilos": "Estilos elegidos", "estilo_otro": "Otro estilo", "voz": "Voz",
             "inspiracion": "Canción de referencia (link)", "historia": "Historia para la letra",
             "evitar": "Lo que NO tiene que aparecer", "duracion": "Duración", "comentarios": "Comentarios"}
FINAL = "\n\nNo ejecutes comandos. Devolvé la respuesta con el formato JSON pedido."
sin_claude = ""          # último motivo por el que no se pudo usar Claude (el bot te avisa una vez)


def respuestas(datos: dict) -> str:
    return "\n".join(f"- {ETIQUETAS.get(k, k)}: {', '.join(v) if isinstance(v, list) else v}"
                     for k, v in datos.items() if v and k in ETIQUETAS)


def instruccion_base(datos: dict) -> str:
    plantilla = PLANTILLA.read_text(encoding="utf-8")
    bloque = re.search(r"## 2\. Instrucción para la IA.*?```\n(.*?)```", plantilla, re.S).group(1)
    return bloque.replace("[PEGAR ACÁ]", respuestas(datos))


def como_texto(v: dict) -> str:
    return (f"TÍTULO: {v['titulo']}\nESTILO: {v['estilo']}\nEXCLUIR: {v['excluir']}\n"
            f"FONÉTICAS: {v['foneticas']}\nLETRA:\n{v['letra']}")


def que_cambia(c: dict) -> str:
    partes = [n for n, k in (("la letra", "cambia_letra"), ("el estilo", "cambia_estilo"), ("el título", "cambia_titulo"))
              if c[k]]
    return " y ".join(partes) if partes else "nada"


def segunda_ia(prompt: str, esquema: dict) -> tuple[dict, str]:
    global sin_claude
    try:
        r = claudecli.correr_json(prompt, esquema)
        sin_claude = ""
        return r, "Claude"
    except claudecli.SinClaude as e:
        sin_claude = str(e)
        log.warning("Claude no disponible (%s): lo hace Codex", e)
        return correr_json(prompt + FINAL, esquema), "Codex"


# ---------------- 1. versión nueva ----------------
def escribir(datos: dict) -> dict:
    """Codex escribe; con link de referencia busca en internet cómo suena para traducirlo a etiquetas."""
    return correr_json(instruccion_base(datos) + FINAL, ESQUEMA_VERSION, buscar=bool(datos.get("inspiracion")),
                       timeout=900)


# ---------------- 2. cambio pedido por el cliente ----------------
def interpretar_cambio(nota: str, datos: dict, anterior: dict) -> dict:
    prompt = f"""Un cliente encargó una canción personalizada, hecha en Suno, y escuchó la vista previa. Pidió este cambio:
«{nota}»

Lo que contó al comprar:
{respuestas(datos)}

La versión que escuchó:
{como_texto(anterior)}

Decidí qué hay que cambiar para cumplir el pedido, y nada más:
- LETRA (las palabras que se cantan): solo si pide algo sobre lo que dice la canción: palabras, nombres, datos, anécdotas, una parte de la historia, cómo se pronuncia una palabra (en Suno se arregla escribiéndola como suena) o el largo. Si dice que la letra está bien, o solo habla de cómo suena, la letra NO cambia.
- ESTILO (cómo suena: género, ritmo, tempo, instrumentos, tipo de voz, energía, producción, "que suene como tal canción o tal artista"): es el campo Style de Suno.
- TÍTULO: solo si lo pide.
En instruccion_letra e instruccion_estilo escribí qué hacer, concreto (vacío si esa parte no cambia). Si nombra una canción o un artista, ponelo tal cual en instruccion_estilo: después se busca cómo suena. En "resumen", una línea para el dueño del negocio: qué pidió el cliente y qué se cambia."""
    c, quien = segunda_ia(prompt, ESQUEMA_CAMBIO)
    c["quien"] = quien
    return c


def conservar(anterior: dict, nueva: dict, cambio: dict) -> dict:
    """Lo que el cliente no pidió cambiar se copia de la versión anterior, palabra por palabra."""
    v = {c: nueva[c] for c in CAMPOS}
    if not cambio["cambia_letra"]:
        v["letra"], v["foneticas"] = anterior["letra"], anterior["foneticas"]
    if not cambio["cambia_estilo"]:
        v["estilo"], v["excluir"] = anterior["estilo"], anterior["excluir"]
    if not cambio["cambia_titulo"]:
        v["titulo"] = anterior["titulo"] or v["titulo"]
    return v


def aplicar_cambio(datos: dict, anterior: dict, nota: str, cambio: dict) -> dict:
    letra = (f"CAMBIO EN LA LETRA: {cambio['instruccion_letra']}\nCambiá solo los versos necesarios para eso; el resto "
             "de la letra queda igual, palabra por palabra." if cambio["cambia_letra"]
             else "LA LETRA NO SE TOCA: devolvela exactamente igual, con las fonéticas.")
    estilo = (f"CAMBIO EN EL ESTILO: {cambio['instruccion_estilo']}\nReescribí el estilo y el excluir siguiendo las "
              "reglas de ESTILO. Si nombra una canción o un artista, buscalo en internet y describí cómo suena (género, "
              "época, tempo, estructura, instrumentos, voz, producción) sin nombrarlo." if cambio["cambia_estilo"]
              else "EL ESTILO NO SE TOCA: devolvé el estilo y el excluir exactamente iguales.")
    titulo = "" if cambio["cambia_titulo"] else "El título queda igual."
    prompt = (f"{instruccion_base(datos)}\n\nYa escribiste esta versión y el cliente la escuchó:\n{como_texto(anterior)}"
              f"\n\nEl cliente pidió: «{nota}»\n\n{letra}\n\n{estilo}\n\n{titulo}")
    nueva = correr_json(prompt + FINAL, ESQUEMA_VERSION, buscar=cambio["cambia_estilo"], timeout=900)
    return conservar(anterior, nueva, cambio)


# ---------------- 3. revisión de la segunda IA ----------------
def prompt_revision(datos: dict, version: dict, anterior: dict | None, nota: str | None, cambio: dict | None) -> str:
    contexto = ""
    if cambio and anterior:
        contexto = (f"\nESTA VERSIÓN ES UN CAMBIO. El cliente escuchó la anterior y pidió: «{nota}».\n"
                    f"Se decidió cambiar {que_cambia(cambio)}. Revisá y corregí SOLO eso, y que el pedido esté bien "
                    f"aplicado: lo demás ya lo escuchó el cliente y queda igual.\n\nVERSIÓN ANTERIOR:\n{como_texto(anterior)}\n")
    return f"""Sos el segundo par de ojos de un servicio argentino de canciones personalizadas para regalar. Otra IA escribió esta versión para cantar en Suno. Revisala contra lo que contó el cliente y corregí lo que haga falta.

LO QUE CONTÓ EL CLIENTE:
{respuestas(datos)}
{contexto}
VERSIÓN A REVISAR:
{como_texto(version)}

Revisá, en este orden:
1. Fidelidad: nombres y apodos bien escritos; el vínculo y la ocasión correctos; las anécdotas como las contó, sin inventar hechos ni cambiarlos de sentido (si dijo "vino con Sprite", no puede quedar "spray"); nada de lo que pidió evitar. En la LETRA se puede nombrar a quien sea (personas, artistas, bandas, lugares, lo que contó el cliente): si fueron a ver a Almafuerte, mejor que diga "Almafuerte". Los nombres de artistas y canciones solo están prohibidos en el ESTILO.
2. Palabras mal elegidas que cambian el sentido o suenan forzadas por la rima.
3. Para Suno: números en letras; nombres difíciles escritos como se pronuncian (y anotados en fonéticas); etiquetas de sección entre corchetes, una por renglón; ninguna acotación entre paréntesis (Suno la canta); el nombre o el apodo al menos dos veces en el estribillo.
4. Que se pueda cantar: versos de 6 a 10 sílabas, métrica pareja dentro de cada sección, rima simple, estribillo fácil de recordar.
5. Tono: voseo rioplatense, cálido y concreto, sin clichés ("sos mi luz", "ángel del cielo").
6. Estilo: coincide con el género, la voz y la referencia que pidió el cliente; etiquetas en inglés separadas por comas, de 6 a 10, con el género primero; tempo en bpm; nada contradictorio; sin nombres de artistas, canciones ni marcas; máximo 400 caracteres. Excluir: de 0 a 4 cosas.
7. Duración: la estructura corresponde a la duración que eligió.
(No podés abrir links ni escuchar audio: la canción de referencia ya la buscó la otra IA. No lo menciones.)

Corregí directamente en la versión. Lo que está bien queda igual: no reescribas por gusto. Devolvé la versión final completa (aunque no cambies nada) y en "problemas" una línea por cada cosa que corregiste, concreta y en castellano (por ejemplo: "Verso 1: decía 'spray' y el cliente contó 'vino con Sprite'"). Si no había nada para corregir, "problemas" va vacío.
En "observaciones" anotá, para el dueño del negocio, errores que veas en partes que NO podés tocar en esta revisión (por ejemplo, en un cambio de solo estilo, un dato de la letra que no coincide con lo que contó el cliente). Si no hay, va vacío."""


def revisar(datos: dict, version: dict, anterior: dict | None = None, nota: str | None = None,
            cambio: dict | None = None) -> tuple[dict, list, list, str]:
    """Devuelve la versión final, lo que corrigió, lo que vio y no podía tocar (para vos) y quién revisó."""
    r, quien = segunda_ia(prompt_revision(datos, version, anterior, nota, cambio), ESQUEMA_REVISION)
    final = {c: r[c] for c in CAMPOS}
    if cambio and anterior:
        final = conservar(anterior, final, cambio)
    return final, [p for p in r["problemas"] if p.strip()], [o for o in r["observaciones"] if o.strip()], quien


# ---------------- archivos de cada versión ----------------
def leer_version(carpeta_letra: pathlib.Path, n: int) -> dict | None:
    js = carpeta_letra / f"version-v{n}.json"
    if js.exists():
        return json.loads(js.read_text(encoding="utf-8"))
    txt = carpeta_letra / f"letra-v{n}.txt"
    if not txt.exists():
        return None
    v = {c: "" for c in CAMPOS}                    # pedidos de antes del 13/10: solo había letra-vN.txt y suno.txt
    v["letra"] = txt.read_text(encoding="utf-8")
    suno = carpeta_letra / "suno.txt"
    if suno.exists():
        s = suno.read_text(encoding="utf-8")
        if m := re.search(r"TÍTULO: (.*)", s):
            v["titulo"] = m.group(1).strip()
        if m := re.search(r"STYLE OF MUSIC:\n(.*?)\n\n", s, re.S):
            v["estilo"] = m.group(1).strip()
    return v


def guardar_version(carpeta_letra: pathlib.Path, n: int, v: dict, extra: dict, novedad: str = ""):
    carpeta_letra.mkdir(parents=True, exist_ok=True)
    (carpeta_letra / f"letra-v{n}.txt").write_text(v["letra"], encoding="utf-8")
    (carpeta_letra / f"version-v{n}.json").write_text(json.dumps({**v, **extra}, indent=2, ensure_ascii=False),
                                                      encoding="utf-8")
    excluir = f"\n\nEXCLUDE STYLES (en Más opciones):\n{v['excluir']}" if v["excluir"].strip() else ""
    (carpeta_letra / "suno.txt").write_text(
        f"TÍTULO: {v['titulo']}\n" + (f"QUÉ CAMBIA EN LA v{n}: {novedad}\n" if novedad else "")
        + f"\nSTYLE OF MUSIC:\n{v['estilo']}{excluir}\n\nLYRICS:\n{v['letra']}\n\nFONÉTICA: {v['foneticas'] or '-'}",
        encoding="utf-8")
