"""Google Drive con el permiso drive.file: la tienda solo ve las carpetas y archivos que ella misma crea."""
import json
import mimetypes
import pathlib

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
CARPETA = "application/vnd.google-apps.folder"


class Drive:
    def __init__(self, token_archivo: str):
        self.token_archivo = pathlib.Path(token_archivo)
        datos = json.loads(self.token_archivo.read_text(encoding="utf-8"))
        self.raiz = datos.get("carpeta_pedidos_id")
        self.cred = Credentials.from_authorized_user_info(datos, SCOPES)
        self._svc = None

    @property
    def svc(self):
        if not self.cred.valid:
            self.cred.refresh(Request())
        if self._svc is None:
            self._svc = build("drive", "v3", credentials=self.cred, cache_discovery=False)
        return self._svc

    def carpeta(self, nombre: str, padre: str | None = None) -> dict:
        cuerpo = {"name": nombre, "mimeType": CARPETA, "parents": [padre or self.raiz]}
        return self.svc.files().create(body=cuerpo, fields="id,webViewLink").execute()

    def buscar_carpeta(self, nombre: str, padre: str) -> dict | None:
        nombre_q = nombre.replace("'", "\\'")
        q = f"name='{nombre_q}' and '{padre}' in parents and mimeType='{CARPETA}' and trashed=false"
        r = self.svc.files().list(q=q, fields="files(id,webViewLink)").execute().get("files", [])
        return r[0] if r else None

    def subir(self, ruta, padre: str, nombre: str | None = None) -> dict:
        ruta = pathlib.Path(ruta)
        mime = mimetypes.guess_type(ruta.name)[0] or "application/octet-stream"
        media = MediaFileUpload(str(ruta), mimetype=mime, resumable=ruta.stat().st_size > 5_000_000)
        return self.svc.files().create(body={"name": nombre or ruta.name, "parents": [padre]},
                                       media_body=media, fields="id,webViewLink").execute()

    def papelera(self, archivo_id: str):
        """A la papelera (Google la vacía sola a los 30 días; mientras tanto se puede recuperar)."""
        self.svc.files().update(fileId=archivo_id, body={"trashed": True}).execute()

    def compartir_con_link(self, archivo_id: str):
        self.svc.permissions().create(fileId=archivo_id, body={"type": "anyone", "role": "reader"}).execute()

    def listar(self, padre: str) -> list[dict]:
        q = f"'{padre}' in parents and trashed=false"
        return self.svc.files().list(q=q, fields="files(id,name,mimeType,size)").execute().get("files", [])

    def descargar(self, archivo_id: str, destino):
        from googleapiclient.http import MediaIoBaseDownload
        with open(destino, "wb") as f:
            baja = MediaIoBaseDownload(f, self.svc.files().get_media(fileId=archivo_id))
            listo = False
            while not listo:
                _, listo = baja.next_chunk()
