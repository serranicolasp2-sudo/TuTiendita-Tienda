"""Mails (Gmail con contraseña de aplicación) y avisos al celular (ntfy)."""
import smtplib
import urllib.parse
from email.message import EmailMessage

import httpx


def mandar_mail(cfg, para: str, asunto: str, texto: str, html: str | None = None, responder_a: str | None = None):
    msg = EmailMessage()
    msg["From"] = f"Tu Canción · Restauración de fotos <{cfg.smtp_user}>"
    msg["To"] = para
    msg["Subject"] = asunto
    if responder_a:
        msg["Reply-To"] = responder_a
    msg.set_content(texto)
    if html:
        msg.add_alternative(html, subtype="html")
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as s:
        s.starttls()
        s.login(cfg.smtp_user, cfg.smtp_password)
        s.send_message(msg)


def avisar(cfg, titulo: str, mensaje: str, acciones: list[dict] | None = None, prioridad: int = 4, tags=("tada",)):
    if not cfg.ntfy_topic:
        return
    cuerpo = {"topic": cfg.ntfy_topic, "title": titulo, "message": mensaje, "priority": prioridad,
              "tags": list(tags), "actions": acciones or []}
    httpx.post(f"{cfg.ntfy_servidor}/", json=cuerpo, timeout=15)


def link_whatsapp(numero: str, texto: str) -> str:
    return f"https://wa.me/{numero}?text={urllib.parse.quote(texto)}"


def normalizar_whatsapp(crudo: str) -> str:
    """Deja el número en formato internacional argentino: 549 + área + número (sin 0 ni 15)."""
    d = "".join(c for c in crudo if c.isdigit())
    if d.startswith("549"):
        return d
    if d.startswith("54"):
        d = d[2:]
    if d.startswith("0"):
        d = d[1:]
    # 15 después del código de área (11 15 1234 5678 → 11 1234 5678)
    for area in (4, 3, 2):
        if len(d) == area + 2 + (10 - area) and d[area:area + 2] == "15":
            d = d[:area] + d[area + 2:]
            break
    return "549" + d if len(d) == 10 else d
