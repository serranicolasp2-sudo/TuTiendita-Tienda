"""Pedidos de la tienda desde tu PC: ver, traer a C:\\Pedidos y entregar.

  python pedidos.py lista                 pedidos pagados (pendientes de entrega)
  python pedidos.py traer RF-0001         baja las fotos y los datos de Drive a C:\\Pedidos\\RF\\Pendientes\\RF-0001 - <comprador>
                                          (con las carpetas que usan fotos.py y cancion.py)
  python pedidos.py entregar RF-0001      sube lo terminado, comparte el link y le manda el mail al cliente;
                                          te llega un aviso con el WhatsApp ya escrito
                                          (fotos: 3-entrega\\*-final.jpg · canción: 4-entrega\\*.mp3 · o pasá los archivos)
  python pedidos.py cambio RF-0001 "..."  si el bot frenó un pedido de cambio que no entendió: le das vos la
                                          instrucción y rehace la foto con ella en la próxima vuelta
  python pedidos.py transferencia RF-0001 el cliente pagó por transferencia: viste el comprobante y la plata
                                          entró → el pedido pasa a pagado y entra en producción
  python pedidos.py interesados           quienes empezaron un pedido y no lo pagaron (nombre, mail y WhatsApp)
  python pedidos.py link-ml 2000012345678 compra de Mercado Libre: link de un solo uso al formulario (sin pago) y el
                                          mensaje para el chat de ML. El producto sale de la orden (o pasalo: … rf-pack-5)

Lee TIENDA_ADMIN_TOKEN de claves-tienda.txt y la llave de Drive de drive_token.json (los dos en el Escritorio).
"""
import os
import pathlib
import sys

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "produccion"))
from app.drive import Drive  # noqa: E402
import carpetas  # noqa: E402  (produccion/carpetas.py)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ESCRITORIO = pathlib.Path.home() / "Desktop"
PEDIDOS = carpetas.PEDIDOS
API = os.environ.get("TIENDA_API", "https://campuscfp401avellaneda.com.ar/tutienditaia/api")


def claves():
    datos = {}
    for l in (ESCRITORIO / "claves-tienda.txt").read_text(encoding="utf-8").splitlines():
        if "=" in l:
            k, v = l.split("=", 1)
            datos[k.strip()] = v.strip()
    return datos


def cliente():
    token = claves().get("TIENDA_ADMIN_TOKEN")
    if not token:
        sys.exit("Falta TIENDA_ADMIN_TOKEN en claves-tienda.txt")
    return httpx.Client(base_url=API, timeout=300, headers={"Authorization": f"Bearer {token}"})


def lista():
    with cliente() as c:
        for p in c.get("/admin/pedidos", params={"estado": "pagado"}).raise_for_status().json():
            aviso = f" ⚠ {p['error']}" if p["error"] else ""
            print(f"{p['id']}  {p['pagado'][:16]}  ${p['precio']:>6}  {p['producto']:<28} {p['nombre']}{aviso}")


def traer(pid):
    pid = pid.upper()
    with cliente() as c:
        p = c.get(f"/admin/pedidos/{pid}").raise_for_status().json()
    if not p.get("drive_carpeta"):
        sys.exit(f"{pid} todavía no tiene carpeta en Drive (estado: {p['estado']}).")
    base = carpetas.carpeta(pid, "Pendientes", p["nombre"])
    es_cancion = p["producto"].startswith("tc-")
    subcarpetas = ("1-datos", "1-original", "2-letra", "3-vistas-previas", "4-entrega") if es_cancion \
        else ("1-original", "2-codex", "3-entrega")
    for s in subcarpetas:
        (base / s).mkdir(parents=True, exist_ok=True)
    (base / ("1-datos" if es_cancion else ".") / "pedido.txt").write_text(p["resumen"], encoding="utf-8")
    if not (base / carpetas.HISTORIAL).exists():
        carpetas.anotar(base, f"PEDIDO {pid} (lo que pidió el cliente)\n{p['resumen']}")
    drive = Drive(str(ESCRITORIO / "drive_token.json"))
    originales = drive.buscar_carpeta("originales", p["drive_carpeta"])
    n = 0
    if originales:
        for f in drive.listar(originales["id"]):
            destino = base / "1-original" / f["name"]
            if not destino.exists():
                drive.descargar(f["id"], destino)
                n += 1
    print(f"{pid} listo en {base}\n  {n} foto(s) nuevas · datos en pedido.txt\n\n{p['resumen']}")


def cambio(pid, texto):
    pid = pid.upper()
    base = carpetas.buscar(pid, "Pendientes")
    if not base:
        sys.exit(f"No encuentro {pid} en Pendientes (C:\\Pedidos\\RF o TC).")
    if not texto.strip():
        sys.exit('Escribí la instrucción entre comillas: python pedidos.py cambio RF-0001 "el vestido era celeste"')
    (base / "nota-cambio.txt").write_text(texto.strip(), encoding="utf-8")
    carpetas.anotar(base, f"Instrucción tuya para rehacer (pedidos.py cambio): {texto.strip()}")
    print(f"Listo. El bot rehace {pid} con: {texto.strip()}")


def entregar(pid, archivos):
    pid = pid.upper()
    base = carpetas.buscar(pid, "Pendientes") or carpetas.carpeta(pid)
    if not archivos:
        archivos = sorted((base / "3-entrega").glob("*-final.jpg")) + sorted((base / "4-entrega").glob("*.mp3")) \
            + sorted((base / "4-entrega").glob("*.mp4"))
    archivos = [pathlib.Path(a) for a in archivos]
    if not archivos:
        sys.exit("No encontré archivos para entregar (3-entrega\\*-final.jpg o 4-entrega\\*.mp3).")
    print("Se entregan:\n  " + "\n  ".join(a.name for a in archivos))
    if input("¿Confirmás? (s/n) ").strip().lower() != "s":
        sys.exit("Cancelado.")
    abiertos = [("archivos", (a.name, open(a, "rb"))) for a in archivos]
    try:
        with cliente() as c:
            r = c.post(f"/admin/pedidos/{pid}/entrega", files=abiertos).raise_for_status().json()
    finally:
        for _, (_, f) in abiertos:
            f.close()
    carpetas.anotar(base, "Entregado a mano (pedidos.py entregar): " + ", ".join(a.name for a in archivos))
    print(f"Entregado. Link: {r['link']}\nMail enviado. Te llegó un aviso con el WhatsApp para mandarle.")


def transferencia(pid):
    """Viste el comprobante y la plata entró: el pedido pasa a pagado y arranca como cualquier pago."""
    pid = pid.upper()
    with cliente() as c:
        p = c.get(f"/admin/pedidos/{pid}").raise_for_status().json()
    print(f"{p['id']} · {p['producto']} · ${p['precio']:,} · {p['nombre']} · estado: {p['estado']}".replace(",", "."))
    if input("¿Viste el comprobante y la plata entró a la cuenta? (s/n) ").strip().lower() != "s":
        sys.exit("Cancelado: el pedido sigue esperando el pago.")
    with cliente() as c:
        r = c.post(f"/admin/pedidos/{pid}/transferencia")
    if r.status_code == 409:
        sys.exit(r.json().get("detail", "El pedido ya no está esperando el pago."))
    r.raise_for_status()
    d = r.json()
    aviso = f"  ⚠ {d['error']}" if d.get("error") else ""
    print(f"Listo: {pid} quedó pagado por transferencia y entró en producción. Te llega el aviso al celular.{aviso}")


def link_ml(orden, producto=None):
    """Compra hecha en Mercado Libre: link de un solo uso al formulario (sin pago) para que mande la foto o la historia.
    El producto sale de la orden de ML; si no se puede leer, pasalo a mano (rf-foto-1, rf-pack-5, tc-cancion, …)."""
    orden = "".join(ch for ch in str(orden) if ch.isdigit())
    if not orden:
        sys.exit("Pasá el número de orden de Mercado Libre: python pedidos.py link-ml 2000012345678")
    if not producto:
        try:
            import ml_api
            import precios_ml
            o = ml_api.get(f"/orders/{orden}")
            titulos = [it["item"]["title"] for it in o.get("order_items", [])]
            productos = {precios_ml.producto(t) for t in titulos} - {None}
            if o.get("status") != "paid":
                sys.exit(f"La orden {orden} está {o.get('status')}: el link se da cuando está pagada.")
            if len(productos) != 1:
                sys.exit(f"No pude saber el producto de la orden ({', '.join(titulos) or 'sin ítems'}). "
                         f"Pasalo a mano: python pedidos.py link-ml {orden} rf-foto-1")
            producto = productos.pop()
        except SystemExit:
            raise
        except Exception as e:
            sys.exit(f"No pude leer la orden en Mercado Libre ({e}). Pasá el producto a mano: "
                     f"python pedidos.py link-ml {orden} rf-foto-1")
    with cliente() as c:
        r = c.post("/admin/canjes", json={"tipo": "mercadolibre", "producto": producto, "orden": orden})
    if r.status_code == 422:
        sys.exit(r.json().get("detail", "No se pudo crear el link."))
    r.raise_for_status()
    d = r.json()
    vence = d["vence"][:10]
    print(f"{'Link nuevo' if d['nuevo'] else 'Ya había un link sin usar para esa orden'} · {producto} · "
          f"vence el {vence[8:10]}/{vence[5:7]} · se usa una sola vez:\n{d['link']}\n")
    print("Mensaje para mandarle por el chat de Mercado Libre:\n"
          "¡Gracias por tu compra! Para empezar, completá este formulario y mandanos "
          f"{'la historia' if producto.startswith('tc-') else 'la foto'} (ya está pago, no se cobra de nuevo): "
          f"{d['link']}")
    print("\nOjo: Mercado Libre puede frenar mensajes con links. Si no lo deja pasar, pedile la foto por el chat como siempre.")


def interesados():
    """Quienes empezaron un pedido y no lo pagaron (uno por mail; sin los que después compraron)."""
    with cliente() as c:
        lista_ = c.get("/admin/interesados").raise_for_status().json()
    if not lista_:
        print("No hay interesados sin compra.")
        return
    for i in lista_:
        transf = " · avisó transferencia" if i.get("transferencia_avisada") else ""
        print(f"{i['creado'][:16]}  {i['pedido']}  ${i['precio']:>6}  {i['producto']:<24} {i['nombre']} · "
              f"{i['email']} · +{i['whatsapp']}{transf}")
    print(f"\n{len(lista_)} interesado(s).")


if __name__ == "__main__":
    comandos = ("lista", "traer", "entregar", "cambio", "transferencia", "interesados", "link-ml")
    if len(sys.argv) < 2 or sys.argv[1] not in comandos:
        sys.exit(__doc__)
    if sys.argv[1] == "lista":
        lista()
    elif sys.argv[1] == "interesados":
        interesados()
    elif len(sys.argv) < 3:
        sys.exit(__doc__)
    elif sys.argv[1] == "traer":
        traer(sys.argv[2])
    elif sys.argv[1] == "cambio":
        cambio(sys.argv[2], " ".join(sys.argv[3:]))
    elif sys.argv[1] == "transferencia":
        transferencia(sys.argv[2])
    elif sys.argv[1] == "link-ml":
        link_ml(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    else:
        entregar(sys.argv[2], sys.argv[3:])
