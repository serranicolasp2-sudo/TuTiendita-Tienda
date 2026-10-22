"""Vigilante de proveedores: desde el 13/10 corre en el SERVIDOR (app/vigilante.py), cada 30 minutos, dentro del
servicio de la tienda; la configuración está en app/proveedores.json. Desde la PC queda:

  python proveedores.py revisar     lee ahora las publicaciones y muestra lo que ve (no ajusta ni avisa)
El bot de la PC usa link_compra() para el aviso "Comprar cuadro".
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.vigilante import link_compra, publicaciones, Vigilante  # noqa: E402,F401

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1 and sys.argv[1] == "revisar":
        import tempfile
        Vigilante(pathlib.Path(tempfile.mkdtemp()) / "estado.json", avisar=lambda *a: None, vigentes=lambda: {},
                  ajustar=lambda *a: None).revisar(forzar=True, prueba=True)
    else:
        sys.exit(__doc__)
