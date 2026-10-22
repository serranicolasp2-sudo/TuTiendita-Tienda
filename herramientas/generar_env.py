"""Genera el .env del servidor a partir de claves-tienda.txt, solo con las líneas KEY=valor que la tienda usa.

  python generar_env.py
  → crea Desktop\\env-servidor.txt (finales de línea de Linux, sin notas sueltas ni contraseñas del servidor)
    que se sube tal cual como /srv/tutienditaia/.env

No muestra ningún valor: solo dice qué clave está y cuántos caracteres tiene.
"""
import pathlib
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ESCRITORIO = pathlib.Path.home() / "Desktop"
NECESARIAS = ["MP_ACCESS_TOKEN", "MP_PUBLIC_KEY", "MP_WEBHOOK_SECRET", "MP_ACCESS_TOKEN_PRUEBA", "MP_PUBLIC_KEY_PRUEBA",
              "SMTP_USER", "SMTP_APP_PASSWORD", "WHATSAPP_NEGOCIO", "NTFY_TOPIC", "TIENDA_ADMIN_TOKEN"]
SERVIDOR = {
    "MP_MODO": "produccion",
    "URL_PUBLICA": "https://campuscfp401avellaneda.com.ar",
    "RUTA_API": "/tutienditaia/api",
    "DATOS_DIR": "/srv/tutienditaia/datos",
    "DRIVE_TOKEN_ARCHIVO": "/srv/tutienditaia/secretos/drive_token.json",
}

claves = {}
for linea in (ESCRITORIO / "claves-tienda.txt").read_text(encoding="utf-8-sig").splitlines():
    linea = linea.strip()
    if "=" in linea and not linea.startswith("#"):
        k, v = linea.split("=", 1)
        k, v = k.strip(), v.strip()
        if k in NECESARIAS and v and k not in claves:   # vale la primera aparición
            claves[k] = v

faltan = [k for k in NECESARIAS if k not in claves]
if faltan:
    sys.exit(f"Faltan en claves-tienda.txt: {', '.join(faltan)}")
if not claves["MP_ACCESS_TOKEN"].startswith("APP_USR-"):
    sys.exit("MP_ACCESS_TOKEN no tiene el formato esperado (APP_USR-…)")

salida = ESCRITORIO / "env-servidor.txt"
contenido = "".join(f"{k}={v}\n" for k, v in {**claves, **SERVIDOR}.items())
salida.write_bytes(contenido.encode("utf-8"))      # \n de Linux, sin BOM
for k in NECESARIAS:
    print(f"{k:24} ok ({len(claves[k])} caracteres)")
print(f"\nListo: {salida}\nSubilo como /srv/tutienditaia/.env (dueño tienda, permisos 600) y reiniciá el servicio.")
