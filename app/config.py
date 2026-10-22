"""Configuración de la tienda. Lee variables de entorno y, si CLAVES_ARCHIVO apunta a un archivo
KEY=valor (como claves-tienda.txt o el .env del servidor), completa con eso lo que no esté en el entorno."""
import os
import pathlib
from dataclasses import dataclass


def _leer_claves(ruta: str | None) -> dict:
    if not ruta:
        return {}
    p = pathlib.Path(ruta)
    if not p.exists():
        return {}
    datos = {}
    for linea in p.read_text(encoding="utf-8", errors="replace").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        datos[k.strip()] = v.strip().strip('"').strip("'")
    return datos


@dataclass
class Config:
    mp_modo: str
    mp_access_token: str
    mp_webhook_secret: str
    smtp_user: str
    smtp_password: str
    whatsapp_negocio: str
    ntfy_topic: str
    drive_token_archivo: str
    datos_dir: pathlib.Path
    url_publica: str          # https://campuscfp401avellaneda.com.ar
    ruta_api: str             # /tutienditaia/api
    url_web_tc: str           # https://…/tutienditaia/tucancion
    url_web_rf: str           # https://…/tutienditaia/restauraciondefotos
    admin_token: str
    aviso_email: str
    ntfy_servidor: str = "https://ntfy.sh"
    url_revision: str = ""    # https://…/tutienditaia/revisar (Nginx lo pasa a la API)
    # Pago por transferencia (pedido del usuario, 17/10): se muestra cuando el pago con Mercado Pago no se completa
    transferencia_alias: str = "tutiendita.ia"
    transferencia_cbu: str = "0000003100082867824654"
    minutos_aviso_sin_pago: int = 30   # a los cuántos minutos sin pagar te llega el aviso al celular

    @property
    def url_webhook(self) -> str:
        return f"{self.url_publica}{self.ruta_api}/mp/webhook?source_news=webhooks"

    def url_web(self, marca: str) -> str:
        return self.url_web_tc if marca == "tc" else self.url_web_rf


def cargar() -> Config:
    archivo = _leer_claves(os.environ.get("CLAVES_ARCHIVO"))

    def v(nombre, defecto=""):
        # strip(): un .env escrito en Windows deja un retorno de carro (\r) al final de cada valor y rompe tokens y firmas
        return (os.environ.get(nombre) or archivo.get(nombre) or defecto).strip().strip('"').strip("'")

    modo = v("MP_MODO", "prueba").lower()
    token = v("MP_ACCESS_TOKEN") if modo == "produccion" else v("MP_ACCESS_TOKEN_PRUEBA")
    publica = v("URL_PUBLICA", "https://campuscfp401avellaneda.com.ar").rstrip("/")
    smtp_user = v("SMTP_USER")
    return Config(
        mp_modo=modo,
        mp_access_token=token,
        mp_webhook_secret=v("MP_WEBHOOK_SECRET"),
        smtp_user=smtp_user,
        smtp_password=v("SMTP_APP_PASSWORD").replace(" ", ""),
        whatsapp_negocio="".join(c for c in v("WHATSAPP_NEGOCIO") if c.isdigit()),
        ntfy_topic=v("NTFY_TOPIC"),
        drive_token_archivo=v("DRIVE_TOKEN_ARCHIVO"),
        datos_dir=pathlib.Path(v("DATOS_DIR", "./datos")),
        url_publica=publica,
        ruta_api=v("RUTA_API", "/tutienditaia/api"),
        url_web_tc=v("URL_WEB_TC", f"{publica}/tutienditaia/tucancion").rstrip("/"),
        url_web_rf=v("URL_WEB_RF", f"{publica}/tutienditaia/restauraciondefotos").rstrip("/"),
        admin_token=v("TIENDA_ADMIN_TOKEN"),
        aviso_email=v("AVISO_EMAIL", smtp_user),
        ntfy_servidor=v("NTFY_SERVIDOR", "https://ntfy.sh").rstrip("/"),
        url_revision=v("URL_REVISION", f"{publica}/tutienditaia/revisar").rstrip("/"),
        transferencia_alias=v("TRANSFERENCIA_ALIAS", "tutiendita.ia"),
        transferencia_cbu="".join(c for c in v("TRANSFERENCIA_CBU", "0000003100082867824654") if c.isdigit()),
        minutos_aviso_sin_pago=int(v("MINUTOS_AVISO_SIN_PAGO", "30") or 30),
    )
