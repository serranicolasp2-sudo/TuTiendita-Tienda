"""Autoriza a la tienda a usar Google Drive (una sola vez, en tu PC).

1. Guardá el archivo del cliente OAuth en el Escritorio como client_secret_tienda.json (ver docs/CLAVES.md).
2. python autorizar_drive.py
3. Se abre el navegador: entrá con el Gmail DEL NEGOCIO y aceptá.
4. Queda drive_token.json en el Escritorio, y en tu Drive aparece la carpeta "Pedidos Tienda".
   Ese archivo es la llave de Drive: va al servidor junto con las otras claves. No lo compartas.

Permiso pedido: drive.file. La tienda solo ve y toca los archivos y carpetas que ella misma crea; el resto de tu Drive le queda invisible.
"""
import json, pathlib, sys

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ESCRITORIO = pathlib.Path.home() / "Desktop"
CLIENTE = ESCRITORIO / "client_secret_tienda.json"
TOKEN = ESCRITORIO / "drive_token.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
CARPETA = "Pedidos Tienda"

if not CLIENTE.exists():
    sys.exit(f"No encuentro {CLIENTE}. Descargá el JSON del cliente OAuth (tipo 'App de escritorio') y guardalo con ese nombre.")

flow = InstalledAppFlow.from_client_secrets_file(str(CLIENTE), SCOPES)
cred = flow.run_local_server(port=0, prompt="consent", access_type="offline")
if not cred.refresh_token:
    sys.exit("Google no devolvió un refresh token. Borrá el acceso de la app en myaccount.google.com/permissions y repetí.")

drive = build("drive", "v3", credentials=cred)
existentes = drive.files().list(q=f"name='{CARPETA}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                                fields="files(id,name)").execute().get("files", [])
carpeta = existentes[0] if existentes else drive.files().create(
    body={"name": CARPETA, "mimeType": "application/vnd.google-apps.folder"}, fields="id,name").execute()
cuenta = drive.about().get(fields="user(emailAddress)").execute()["user"]["emailAddress"]

datos = json.loads(cred.to_json())
datos["carpeta_pedidos_id"] = carpeta["id"]
TOKEN.write_text(json.dumps(datos, indent=2), encoding="utf-8")
print(f"Listo. Cuenta: {cuenta}\nCarpeta '{CARPETA}' en Drive (id {carpeta['id']}).\nLlave guardada en {TOKEN}")
