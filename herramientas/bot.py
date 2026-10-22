"""Bot de producción de Tu Tiendita IA. Corre en tu PC y hace solo:

FOTOS:     pedido pagado → baja las fotos → Codex analiza cada una y busca referencias de color en internet
           (restauracion.py) → Codex la restaura con esa ficha → Real-ESRGAN → vista previa al cliente (mail +
           página para aprobar o pedir 1 cambio) → si pide un cambio, Codex primero valida el comentario: si tiene
           sentido rehace desde el original con esa instrucción; si no, te avisa con el WhatsApp ya escrito y
           espera (`pedidos.py cambio RF-XXXX "..."` para rehacer igual) → cuando aprueba, entrega la versión final.
           Cuadros: después de aprobar, te avisa con el link del proveedor y la dirección para que compres el cuadro.
CANCIONES: pedido pagado → Codex escribe la letra y el estilo para Suno, Claude (con tu suscripción; si no hay
           sesión, Codex) la revisa contra lo que contó el cliente y corrige (2-letra\\suno.txt) y te avisa.
           Vos: Suno + `cancion.py previa`. El bot sube la vista previa sola. Si el cliente pide un cambio, primero
           se decide qué cambia (letra, estilo o título) y se toca SOLO eso (letras.py); te avisa qué cambió. Cuando aprueba: vos descargás de Suno y corrés `cancion.py final`;
           el bot entrega solo (en el combo, arma también el video con las fotos).

Uso:  python bot.py            (queda corriendo; revisa cada 60 s)
      python bot.py una-vez    (una sola pasada, para probar)
Carpetas: C:\\Pedidos\\RF|TC\\Pendientes|Listos\\<pedido> - <comprador>\\ con historial.txt (carpetas.py).
Registro: C:\\Pedidos\\bot.log · Estado: C:\\Pedidos\\bot-estado.json (borrá la entrada de un pedido para reintentarlo)
"""
import concurrent.futures
import json
import logging
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time

import httpx
from PIL import Image
from urllib.parse import quote

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parents[1] / "produccion"))
import carpetas  # noqa: E402  (produccion/carpetas.py)
import fotos  # noqa: E402  (produccion/fotos.py)
import letras  # noqa: E402  (herramientas/letras.py)
import pedidos  # noqa: E402  (herramientas/pedidos.py)
import restauracion  # noqa: E402  (herramientas/restauracion.py)
import proveedores  # noqa: E402  (herramientas/proveedores.py)
from codexcli import correr_codex, imagenes  # noqa: E402

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PEDIDOS = pedidos.PEDIDOS
ESTADO = PEDIDOS / "bot-estado.json"
GENERADAS = pathlib.Path.home() / ".codex" / "generated_images"
PROMPTS = AQUI.parents[1] / "produccion" / "prompts"
INTERVALO = 60
MAX_INTENTOS = 3
DIAS_RETENCION = 30   # igual que el servidor y las condiciones de las webs
FOTOS_RESTAURADAS_COMBO = 3
INTENTOS_CAMBIO = 2   # si Codex no aplica un cambio pedido, cuántas veces lo intenta antes de frenar
PARALELO = 3          # fotos que Codex restaura a la vez (pack de 20 en menos de 2 h)

PEDIDOS.mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                    handlers=[logging.FileHandler(PEDIDOS / "bot.log", encoding="utf-8"), logging.StreamHandler(sys.stdout)])
log = logging.getLogger("bot")
logging.getLogger("httpx").setLevel(logging.WARNING)      # sin una línea por cada consulta al servidor


# ---------------- utilidades ----------------
def leer_estado() -> dict:
    try:
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def guardar_estado(e: dict):
    tmp = ESTADO.with_suffix(".tmp")
    tmp.write_text(json.dumps(e, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(ESTADO)


def avisar(titulo, mensaje, acciones=None, prioridad=4, tags=("robot",)):
    topic = pedidos.claves().get("NTFY_TOPIC")
    if not topic:
        return
    try:
        httpx.post("https://ntfy.sh/", timeout=15, json={"topic": topic, "title": titulo, "message": mensaje[:3500],
                                                         "priority": prioridad, "tags": list(tags), "actions": acciones or []})
    except Exception as e:
        log.warning("No pude avisar por ntfy: %s", e)


def a_jpg(ruta: pathlib.Path) -> pathlib.Path:
    """Codex y ffmpeg no siempre leen HEIC o TIFF: se convierten a JPG (el original queda en Drive)."""
    if ruta.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
        return ruta
    destino = ruta.with_suffix(".jpg")
    Image.open(ruta).convert("RGB").save(destino, quality=95)
    ruta.unlink()
    return destino


# ---------------- Codex ----------------
def codex_restaurar(original: pathlib.Path, destino: pathlib.Path, prompt: str, referencia: pathlib.Path | None = None):
    """original: la imagen que Codex edita. referencia: en un cambio, la foto escaneada (solo para comparar caras).
    Las referencias de color van en texto: con la imagen adjunta, Codex copia el dibujo."""
    inicio = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        salida = correr_codex(["-C", tmp, "--json", *imagenes([original, *([referencia] if referencia else [])])], prompt)
    hilo = None
    for linea in salida.splitlines():
        try:
            ev = json.loads(linea)
        except json.JSONDecodeError:
            continue
        hilo = ev.get("thread_id") or ev.get("session_id") or hilo
    candidatas = []
    if hilo and (GENERADAS / hilo).exists():
        candidatas = sorted((GENERADAS / hilo).glob("*.png"), key=lambda p: p.stat().st_mtime)
    if not candidatas and not hilo:     # sin id de hilo: la más nueva (solo si no hay otras corriendo a la vez)
        candidatas = sorted((p for p in GENERADAS.rglob("*.png") if p.stat().st_mtime >= inicio - 2),
                            key=lambda p: p.stat().st_mtime)[-1:]
    if not candidatas:
        raise RuntimeError("Codex no generó ninguna imagen (¿se agotó el cupo de imágenes del plan?)")
    shutil.copy2(candidatas[0], destino)
    for img in candidatas:               # son fotos de clientes: no dejar copias en ~/.codex
        try:
            img.unlink()
        except OSError:
            pass
    if hilo and (GENERADAS / hilo).exists() and not any((GENERADAS / hilo).iterdir()):
        (GENERADAS / hilo).rmdir()


# ---------------- pasos ----------------
def api():
    return pedidos.cliente()


def detalle(pid):
    with api() as c:
        return c.get(f"/admin/pedidos/{pid}").raise_for_status().json()


def asegurar_local(p) -> pathlib.Path:
    base = carpetas.buscar(p["id"], "Pendientes")
    if not base:
        pedidos.traer(p["id"])
        base = carpetas.buscar(p["id"], "Pendientes")
    for f in list((base / "1-original").glob("*")):
        a_jpg(f)
    return base


def subir(pid, ruta_api, archivos, mensaje=""):
    abiertos = [("archivos", (a.name, open(a, "rb"))) for a in archivos]
    try:
        with api() as c:
            return c.post(f"/admin/pedidos/{pid}/{ruta_api}", files=abiertos,
                          data={"mensaje": mensaje}).raise_for_status().json()
    finally:
        for _, (_, f) in abiertos:
            f.close()


def originales_de(base, solo_primeras=None):
    return sorted(f for f in (base / "1-original").glob("*.*") if f.is_file())[: solo_primeras or None]


def ficha_de(p, base, foto) -> dict | None:
    """Análisis de la foto (se hace una vez y queda en 0-analisis). Si falla, se restaura igual con las reglas fijas."""
    ruta = base / "0-analisis" / f"{foto.stem}.json"
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    log.info("%s: Codex analiza %s y busca referencias", p["id"], foto.name)
    try:
        ficha = restauracion.analizar(foto, p["datos"])
    except Exception as e:
        log.warning("%s: no se pudo analizar %s (%s); sigo con las reglas fijas", p["id"], foto.name, e)
        return None
    ruta.parent.mkdir(exist_ok=True)
    ruta.write_text(json.dumps(ficha, indent=2, ensure_ascii=False), encoding="utf-8")
    restauracion.registrar(ficha, p["id"])
    carpetas.anotar(base, f"Análisis de {foto.name} ({ficha['estado_color']}, {ficha['epoca']}): "
                          + ("apta" if ficha["apta"] else f"NO apta: {ficha['motivo']}")
                          + f"\nDaños: {', '.join(d['tipo'] + ' (' + d['gravedad'] + ')' for d in ficha['danos']) or 'ninguno'}"
                          + f"\nFicha completa: 0-analisis\\{ruta.name}")
    if not ficha["apta"]:
        avisar(f"⚠ Revisá {p['id']}: {foto.name}", f"El análisis dice que no es apta: {ficha['motivo']}\n"
               "La restauro igual; mirá la comparativa antes de que el cliente apruebe.", tags=("warning",))
    return ficha


def producir_fotos(p, cambio=None, solo=None, solo_primeras=None, modo_nuevo=None):
    """Restaura desde los originales. solo = stems a rehacer (en un cambio); las demás quedan como estaban."""
    base = asegurar_local(p)
    originales = originales_de(base, solo_primeras)
    if not originales:
        raise RuntimeError("No hay fotos en 1-original")
    (base / "0-analisis").mkdir(exist_ok=True)
    (base / "2-codex" / "anteriores").mkdir(parents=True, exist_ok=True)
    pendientes = [f for f in originales if not solo or f.stem in solo]
    with concurrent.futures.ThreadPoolExecutor(max_workers=PARALELO) as ex:
        list(ex.map(lambda f: restaurar_una(p, base, f, cambio, modo_nuevo), pendientes))   # list(): propaga el primer error
    fotos.procesar(p["id"])
    return base


def restaurar_una(p, base, f, cambio, modo_nuevo=None):
    ficha = ficha_de(p, base, f)
    refs = restauracion.referencias(ficha)
    destino = base / "2-codex" / f"{f.stem}.png"
    n, previa = 1, None
    if destino.exists():                       # la versión anterior se guarda, no se pisa
        n = len(list((base / "2-codex" / "anteriores").glob(f"{f.stem}-v*.png"))) + 2
        previa = base / "2-codex" / "anteriores" / f"{f.stem}-v{n - 1}.png"
        shutil.move(str(destino), str(previa))
    if cambio and previa:
        # El cambio se aplica SOBRE la versión que vio el cliente: lo que no pidió cambiar ya está aprobado.
        # Rehacer desde el original hacía que Codex reinterpretara todo y apareciera un error nuevo (13/10).
        prompt = restauracion.instruccion_cambio(p["datos"], ficha, refs, cambio, modo_nuevo)
        imagen, referencia = previa, f
    else:
        prompt = restauracion.instruccion(p["datos"], ficha, refs, cambio)
        imagen, referencia = f, None
    (base / "0-analisis" / f"{f.stem}-prompt-v{n}.txt").write_text(prompt, encoding="utf-8")
    log.info("%s: Codex %s %s (v%d, %d referencia/s)", p["id"], "edita" if referencia else "restaura", f.name, n, len(refs))
    generar(p, base, f, n, ficha, imagen, destino, prompt, referencia)
    if referencia:
        verificar_cambio(p, base, f, n, ficha, previa, destino, cambio, prompt, imagen, referencia)
    modo = modo_nuevo or p["datos"].get("color") or "-"
    carpetas.anotar(base, f"{f.name}: versión v{n} hecha por Codex "
                          f"({'cambio sobre la v' + str(n - 1) if referencia else 'restauración'}, modo {modo}) "
                          f"→ 2-codex\\{destino.name}"
                          + (f"\nVersión anterior guardada en 2-codex\\anteriores\\{previa.name}" if previa else "")
                          + f"\nPrompt: 0-analisis\\{f.stem}-prompt-v{n}.txt")


def generar(p, base, f, n, ficha, imagen, destino, prompt, referencia=None):
    codex_restaurar(imagen, destino, prompt, referencia)


def verificar_cambio(p, base, f, n, ficha, previa, destino, cambio, prompt, imagen, referencia):
    """Antes de mandar la vista previa, Codex compara la versión anterior con la nueva: si el cambio no se ve, reintenta
    con una orden más firme; si tampoco, frena y avisa (13/10: el pecho negro volvió igual en la segunda entrega)."""
    for intento in range(1, INTENTOS_CAMBIO + 1):
        ver = restauracion.verificar_cambio(previa, destino, cambio)
        (base / "0-analisis" / f"{f.stem}-verificacion-v{n}-{intento}.json").write_text(
            json.dumps(ver, indent=2, ensure_ascii=False), encoding="utf-8")
        if ver["aplicado"]:
            log.info("%s: cambio aplicado en %s (%s)", p["id"], f.name, ver["motivo"])
            carpetas.anotar(base, f"Verificación de {f.name} v{n} (intento {intento}): el cambio SE VE. {ver['motivo']}")
            return
        carpetas.anotar(base, f"Verificación de {f.name} v{n} (intento {intento}): el cambio NO se ve. {ver['motivo']}")
        log.info("%s: el cambio NO se aplicó en %s (%s)", p["id"], f.name, ver["motivo"])
        if intento < INTENTOS_CAMBIO:
            refuerzo = (f"ATENCIÓN: un intento anterior NO aplicó el cambio ({ver['motivo']}). "
                        "Esta vez modificá esa zona de forma clara y visible.")
            generar(p, base, f, n, ficha, imagen, destino, prompt + "\n\n" + refuerzo, referencia)
    shutil.move(str(previa), str(destino))          # vuelve a la versión anterior: no se manda una foto igual
    carpetas.anotar(base, f"FRENADO: Codex no aplicó el cambio en {f.name} tras {INTENTOS_CAMBIO} intentos. "
                          "No se le mandó nada al cliente; quedó la versión anterior.")
    avisar(f"⚠ Codex no aplicó el cambio en {p['id']}",
           f"Pedido del cliente: {cambio}\nLo intentó {INTENTOS_CAMBIO} veces y la foto sale igual ({ver['motivo']}). "
           f"No mandé nada al cliente. Podés darle otra instrucción con: python pedidos.py cambio {p['id']} \"...\"",
           prioridad=5, tags=("warning",))
    raise RuntimeError(f"Codex no aplicó el cambio en {f.name}: {ver['motivo']}")


def mandar_vista_previa_fotos(p, cambio=None, solo=None, modo_nuevo=None):
    base = producir_fotos(p, cambio, solo, modo_nuevo=modo_nuevo)
    previas = sorted((base / "3-entrega").glob("*-vista-previa.jpg"))
    subir(p["id"], "vista-previa", previas)
    log.info("%s: vista previa enviada (%d fotos)", p["id"], len(previas))
    carpetas.anotar(base, "Vista previa enviada al cliente (mail con el link para aprobar o pedir cambio): "
                          + ", ".join(x.name for x in previas))


def escribir_letra(p, est, nota=None):
    """Versión nueva de la letra y el estilo. Con nota (cambio del cliente): se decide qué cambia y se toca solo eso."""
    base = asegurar_local(p)
    carpeta_letra = base / "2-letra"
    n = est.get("letra_n", 0) + 1
    anterior = letras.leer_version(carpeta_letra, n - 1) if n > 1 else None
    cambio, novedad = None, ""
    if nota and anterior:
        cambio = letras.interpretar_cambio(nota, p["datos"], anterior)
        novedad = f"cambia {letras.que_cambia(cambio)}" + ("" if cambio["cambia_letra"] else " (la letra queda igual)")
        carpetas.anotar(base, f"CAMBIO {p.get('cambios') or '?'} PEDIDO POR EL CLIENTE: «{nota}»\n"
                              f"Interpretación ({cambio['quien']}): {novedad}. {cambio['resumen']}"
                              + (f"\nLetra: {cambio['instruccion_letra']}" if cambio["cambia_letra"] else "")
                              + (f"\nEstilo: {cambio['instruccion_estilo']}" if cambio["cambia_estilo"] else ""))
        if not (cambio["cambia_letra"] or cambio["cambia_estilo"] or cambio["cambia_titulo"]):
            avisar(f"🎵 Cambio para revisar {p['id']}", f"El cliente pidió: {nota}\n{cambio['resumen']}\n"
                   "No cambia la letra ni el estilo: mirá vos qué hacer en Suno y grabá otra previa.",
                   prioridad=5, tags=("musical_note",))
            return
        borrador = letras.aplicar_cambio(p["datos"], anterior, nota, cambio)
    else:
        borrador = letras.escribir(p["datos"])
    final, problemas, observaciones, quien = letras.revisar(p["datos"], borrador, anterior if cambio else None, nota,
                                                             cambio)
    if letras.sin_claude and not est.get("aviso_sin_claude"):
        avisar("ℹ Claude no revisó la letra", f"Revisó Codex. Motivo: {letras.sin_claude}\nPara que revise Claude con tu "
               "suscripción: abrí una terminal, escribí claude y adentro /login (una sola vez).", tags=("information_source",))
        est["aviso_sin_claude"] = True
    letras.guardar_version(carpeta_letra, n, final, {"revisor": quien, "correcciones": problemas,
                                                     "observaciones": observaciones,
                                                     "cambio": {"nota": nota, **cambio} if cambio else None}, novedad)
    est["letra_n"] = n
    revision = "\n".join(f"  - {x}" for x in problemas) if problemas else "  sin correcciones"
    ojo = "".join(f"\nOJO (no se tocó, revisalo vos): {o}" for o in observaciones)
    carpetas.anotar(base, f"LETRA v{n} lista ({'cambio: ' + novedad if cambio else 'primera versión'}). "
                          f"Escribió Codex, revisó {quien}:\n{revision}\n"
                          f"Título: {final['titulo']}\nEstilo: {final['estilo']}"
                          + (f"\nExcluir: {final['excluir']}" if final["excluir"].strip() else "")
                          + f"\nArchivos: 2-letra\\letra-v{n}.txt y suno.txt{ojo}")
    motivo = f"Cambio pedido: {nota}\n→ {novedad}\n" if nota else ""
    avisar(f"🎵 Letra lista {p['id']} (v{n})",
           f"{motivo}Revisó {quien} ({len(problemas)} correcciones).{ojo}\nAbrí {carpeta_letra / 'suno.txt'}, pegala en Suno "
           f"(Custom) y después: python cancion.py previa {p['id']}", tags=("musical_note",))
    log.info("%s: letra v%d lista (%s; revisó %s, %d correcciones)", p["id"], n, novedad or "nueva", quien, len(problemas))


def subir_previa_cancion(p, est) -> bool:
    carpeta = carpetas.buscar(p["id"], "Pendientes")
    if not carpeta:
        return False
    previas = sorted((carpeta / "3-vistas-previas").glob("v*-previa.mp3"), key=lambda f: int(re.search(r"v(\d+)", f.name).group(1)))
    if not previas:
        return False
    ultima = previas[-1]
    n = int(re.search(r"v(\d+)", ultima.name).group(1))
    if n <= est.get("previa_subida", 0):
        return False
    subir(p["id"], "vista-previa", [ultima])
    est["previa_subida"] = n
    carpetas.anotar(carpeta, f"Vista previa v{n} enviada al cliente: 3-vistas-previas\\{ultima.name}")
    log.info("%s: vista previa de canción v%d enviada", p["id"], n)
    return True


def video_combo(p, base) -> pathlib.Path:
    mp3 = sorted((base / "4-entrega").glob("*.mp3"))[0]
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp3)],
                               capture_output=True, text=True).stdout.strip() or 180)
    imagenes = []
    for f in sorted((base / "1-original").glob("*.*")):
        final = base / "3-entrega" / f"{f.stem}-final.jpg"
        imagenes.append(final if final.exists() else f)
    cada = dur / len(imagenes)
    lista = base / "4-entrega" / "_lista.txt"
    lista.write_text("".join(f"file '{i.as_posix()}'\nduration {cada:.3f}\n" for i in imagenes)
                     + f"file '{imagenes[-1].as_posix()}'\n", encoding="utf-8")
    salida = base / "4-entrega" / (mp3.stem + " (video).mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lista), "-i", str(mp3),
                    "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,fps=30,format=yuv420p",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-shortest", str(salida)],
                   check=True)
    lista.unlink()
    return salida


def entregar(p, est):
    base = asegurar_local(p)
    if p["producto"].startswith("rf-"):
        archivos = sorted((base / "3-entrega").glob("*-final.jpg"))
    else:
        archivos = sorted((base / "4-entrega").glob("*.mp3"))
        if not archivos:
            if not est.get("aviso_descarga"):
                carpetas.anotar(base, "El cliente APROBÓ la vista previa. Falta la descarga oficial de Suno (cancion.py final).")
                avisar(f"✅ Aprobada {p['id']}: falta descargar",
                       f"Descargá de Suno la versión aprobada y corré: python cancion.py final {p['id']} <archivo> --para \"...\"")
                est["aviso_descarga"] = True
            return
        if p["producto"] == "tc-combo":
            archivos.append(video_combo(p, base))
    subir(p["id"], "entrega", archivos)
    est["entregado"] = True
    carpetas.anotar(base, ("El cliente APROBÓ la vista previa. " if p["producto"].startswith("rf-") else "")
                    + "ENTREGADO (mail con el link de descarga): " + ", ".join(a.name for a in archivos))
    log.info("%s: entregado (%d archivos)", p["id"], len(archivos))
    envio = p["datos"].get("envio")
    if envio:
        link = proveedores.link_compra(p["producto"], p["datos"].get("marco")) or "(proveedor a definir)"
        direccion = (f"{envio['destinatario']} · {envio['calle']} {envio['numero']} {envio.get('piso_depto', '')} · "
                     f"{envio['localidad']}, {envio['provincia']} ({envio['cp']}) · DNI {envio['dni']} · WhatsApp +{p['whatsapp']}")
        marco = f"Marco: {p['datos']['marco']}\n" if p["datos"].get("marco") else ""
        carpetas.anotar(base, f"Falta comprar el cuadro ({p['producto']}). {marco.strip()} Proveedor: {link}")
        avisar(f"🖼 Comprar cuadro {p['id']}",
               f"Foto final en Drive. {marco}Comprá el cuadro con envío a:\n{direccion}\n"
               f"Foto: {carpetas.PEDIDOS / carpetas.tipo(p['id']) / 'Listos' / base.name / '3-entrega'}",
               [{"action": "view", "label": "Abrir proveedor", "url": link}] if link.startswith("http") else None,
               prioridad=5, tags=("frame_with_picture",))
    carpetas.mover_a_listos(p["id"])


def limpiar_listos():
    """Borra de C:\\Pedidos\\RF|TC\\Listos los pedidos terminados hace más de DIAS_RETENCION días (en Drive se purgan solos)."""
    limite = time.time() - DIAS_RETENCION * 86400
    for carpeta in carpetas.listos():
        if carpeta.stat().st_mtime < limite:
            shutil.rmtree(carpeta, ignore_errors=True)
            log.info("%s: borrado de Listos (más de %d días)", carpeta.name, DIAS_RETENCION)


def whatsapp(p, texto):
    return [{"action": "view", "label": "WhatsApp al cliente",
             "url": f"https://wa.me/{p['whatsapp']}?text={quote(texto)}"}] if texto and p.get("whatsapp") else None


def atender_cambio_fotos(p, est, cambios):
    """Antes de rehacer, Codex valida el comentario. Si no tiene sentido, te avisa y espera tu instrucción."""
    base = asegurar_local(p)
    nota = (p.get("nota_cambio") or "").strip()
    manual = base / "nota-cambio.txt"
    (base / "0-analisis").mkdir(exist_ok=True)
    if manual.exists():                                   # la escribiste vos con pedidos.py cambio
        v = {"valida": True, "instruccion": manual.read_text(encoding="utf-8").strip(), "fotos": [],
             "rechazado": "", "mensaje_cliente": ""}
        manual.replace(base / "0-analisis" / f"cambio-{cambios}-manual.txt")
        carpetas.anotar(base, f"CAMBIO {cambios} PEDIDO POR EL CLIENTE: «{nota}»\nSe rehace con tu instrucción: {v['instruccion']}")
    elif est.get("cambio_en_espera") == cambios:
        return                                            # esperando tu decisión
    else:
        originales = originales_de(base)
        previas = [base / "2-codex" / f"{o.stem}.png" for o in originales]
        v = restauracion.validar_cambio(nota, p["datos"], originales,
                                        previas if all(x.exists() for x in previas) else None)
        (base / "0-analisis" / f"cambio-{cambios}.json").write_text(
            json.dumps({"nota": nota, **v}, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("%s: cambio %s (%s) → %s", p["id"], "válido" if v["valida"] else "NO válido", v["categoria"],
                 v["instruccion"] or v["rechazado"])
        carpetas.anotar(base, f"CAMBIO {cambios} PEDIDO POR EL CLIENTE: «{nota}»\n"
                              f"Validación de Codex: {'válido' if v['valida'] else 'NO válido'} ({v['categoria']})"
                              + (f"\nInstrucción: {v['instruccion']}" if v["instruccion"] else "")
                              + (f"\nNo se hace: {v['rechazado']}" if v["rechazado"] else "")
                              + (f"\nModo de color nuevo: {v['modo_color']}" if v.get("modo_color") else ""))
        if not v["valida"] or not v["instruccion"].strip():
            est["cambio_en_espera"] = cambios
            avisar(f"✋ Cambio para revisar {p['id']}",
                   f"El cliente pidió: {nota}\nNo lo rehice: {v['rechazado'] or 'no se entiende'}.\n"
                   f"Escribile (el botón trae el mensaje armado). Para rehacer con tu instrucción:\n"
                   f'python pedidos.py cambio {p["id"]} "..."',
                   whatsapp(p, v["mensaje_cliente"]), prioridad=5, tags=("raised_hand",))
            return
    if v.get("modo_color"):                                # "pasala a color", "dejala en blanco y negro"…
        p = {**p, "datos": {**p["datos"], "color": v["modo_color"]}}
    mandar_vista_previa_fotos(p, cambio=v["instruccion"], solo=restauracion.fotos_del_cambio(v, originales_de(base)),
                              modo_nuevo=v.get("modo_color") or None)
    est["cambio_atendido"] = cambios
    est.pop("cambio_en_espera", None)
    if v.get("rechazado"):
        avisar(f"ℹ Cambio parcial {p['id']}", f"Hice: {v['instruccion']}\nNo hice: {v['rechazado']}",
               whatsapp(p, v.get("mensaje_cliente")), tags=("information_source",))


def paso(p, est):
    pid, estado, prod = p["id"], p["estado"], p["producto"]
    cancion = prod.startswith("tc-")
    if estado == "pagado":
        if cancion:
            if prod == "tc-combo" and not est.get("fotos_combo"):
                producir_fotos(p, solo_primeras=FOTOS_RESTAURADAS_COMBO)
                est["fotos_combo"] = True
            if not est.get("letra_n"):
                escribir_letra(p, est)
            subir_previa_cancion(p, est)
        elif not est.get("vista_n"):
            mandar_vista_previa_fotos(p)
            est["vista_n"] = 1
    elif estado == "cambio":
        cambios = p.get("cambios") or 0
        if cancion:
            if est.get("cambio_atendido") != cambios:
                escribir_letra(p, est, nota=p.get("nota_cambio"))
                est["cambio_atendido"] = cambios
            subir_previa_cancion(p, est)
        elif est.get("cambio_atendido") != cambios:
            atender_cambio_fotos(p, est, cambios)
    elif estado == "aprobado" and not est.get("entregado"):
        entregar(p, est)


def pasada():
    limpiar_listos()
    estado = leer_estado()
    with api() as c:
        activos = [x for x in c.get("/admin/pedidos").raise_for_status().json()
                   if x["estado"] in ("pagado", "cambio", "aprobado")]
    for resumen in reversed(activos):           # del más viejo al más nuevo
        pid = resumen["id"]
        est = estado.setdefault(pid, {})
        if est.get("intentos", 0) >= MAX_INTENTOS:
            base_dir = carpetas.buscar(pid)
            reintentar_txt = (base_dir / "reintentar.txt") if base_dir else None
            if reintentar_txt and reintentar_txt.is_file():
                analisis = base_dir / "0-analisis"
                analisis.mkdir(parents=True, exist_ok=True)
                fecha_str = time.strftime("%Y%m%d-%H%M%S")
                shutil.move(str(reintentar_txt), str(analisis / f"reintentar-{fecha_str}.txt"))
                est["intentos"] = 0
                carpetas.anotar(base_dir, "Reintento pedido desde la centralita")
            else:
                continue
        try:
            paso(detalle(pid), est)
            est["intentos"] = 0
        except Exception as e:
            est["intentos"] = est.get("intentos", 0) + 1
            log.exception("%s: falló (intento %d)", pid, est["intentos"])
            if est["intentos"] >= MAX_INTENTOS:
                carpetas.anotar_pid(pid, f"BOT FRENADO tras {MAX_INTENTOS} intentos: {e}")
                avisar(f"⚠ Bot frenado en {pid}", f"{e}\nRevisá C:\\Pedidos\\bot.log. Para reintentar: botón Reintentar en la centralita (Hoy).",
                       prioridad=5, tags=("warning",))
        finally:
            guardar_estado(estado)


def candado():
    """Una sola copia del bot a la vez: si ya hay otra corriendo, esta se cierra."""
    import msvcrt
    f = open(PEDIDOS / "bot.lock", "a+")
    try:
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        log.info("Ya hay un bot corriendo; esta copia se cierra.")
        sys.exit(0)
    return f  # mantener abierto mientras viva el proceso


def sin_suspension():
    """Mientras el bot corre, Windows no suspende la PC (la pantalla sí se puede apagar). No cambia la
    configuración de energía: es el mismo pedido que hace un reproductor de video y se termina al cerrar el bot."""
    import ctypes
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    if not ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED):
        log.warning("No pude pedirle a Windows que no suspenda la PC")


def main():
    _candado = candado()
    if len(sys.argv) > 1 and sys.argv[1] == "una-vez":
        pasada()
        return
    sin_suspension()
    log.info("Bot iniciado. Revisa cada %d s. La PC no se suspende mientras corre.", INTERVALO)
    while True:
        try:
            pasada()
        except Exception:
            log.exception("Falló la pasada (¿sin internet o el servidor caído?)")
        time.sleep(INTERVALO)


if __name__ == "__main__":
    main()
