"""Catálogo con los precios. El servidor es el único que decide cuánto se cobra: la web solo manda el id del producto.
Precios aprobados en DECISIONES.md (D-03 y D-15)."""
import json
import pathlib
from dataclasses import dataclass, asdict, replace


@dataclass(frozen=True)
class Producto:
    id: str
    marca: str            # "tc" = Tu Canción · "rf" = Restauración de fotos
    nombre: str
    precio: int           # pesos, IVA incluido
    detalle: str
    fotos_min: int = 0
    fotos_max: int = 0
    cancion: bool = False
    envio: bool = False   # cuadro físico: pide dirección de entrega
    marcos: tuple = ()    # colores de marco que el cliente elige (vacío = no lleva marco)
    activo: bool = True

    def publico(self) -> dict:
        return asdict(self)


PRODUCTOS: dict[str, Producto] = {p.id: p for p in [
    Producto("rf-foto-1", "rf", "Restauración de 1 foto", 4_999,
             "Archivo digital en alta calidad, color incluido si lo pedís.", 1, 1),
    Producto("rf-pack-5", "rf", "Pack de 5 fotos restauradas", 14_999,
             "Hasta 5 fotos. Archivos digitales en alta calidad.", 1, 5),
    Producto("rf-pack-10", "rf", "Pack de 10 fotos restauradas", 24_999,
             "Hasta 10 fotos. Archivos digitales en alta calidad.", 1, 10),
    Producto("rf-pack-20", "rf", "Pack de 20 fotos restauradas", 39_999,
             "Hasta 20 fotos. Archivos digitales en alta calidad.", 1, 20),
    Producto("rf-cuadro-ecocuero-20x30", "rf", "Cuadro ecocuero en bastidor 20x30 con tu foto restaurada", 34_999,
             "Restauración, impresión en ecocuero sobre bastidor y envío a domicilio.", 1, 1, envio=True),
    Producto("rf-cuadro-ecocuero-40x30", "rf", "Cuadro ecocuero en bastidor 40x30 con tu foto restaurada", 44_999,
             "Restauración, impresión en ecocuero sobre bastidor y envío a domicilio.", 1, 1, envio=True),
    Producto("rf-cuadro-enmarcado-20x30", "rf", "Cuadro enmarcado 20x30 con tu foto restaurada", 24_999,
             "Restauración, impresión enmarcada (marco color madera o negro) y envío a domicilio.", 1, 1, envio=True,
             marcos=("Madera", "Negro")),
    # 30x40: el tamaño más grande que la restauración imprime a 300 dpi (fotos.py, LADO_MAX_FINAL = 4800). Precio inicial
    # con la comisión real de MP del 14/10 (4,30 %): (23.000 + 5.000) / 0,957 → $29.999; después lo ajusta el vigilante.
    Producto("rf-cuadro-enmarcado-30x40", "rf", "Cuadro enmarcado 30x40 con tu foto restaurada", 29_999,
             "Restauración, impresión enmarcada (marco color madera o negro) y envío a domicilio.", 1, 1, envio=True,
             marcos=("Madera", "Negro")),
    Producto("tc-cancion", "tc", "Canción con tu historia", 26_999,
             "MP3 con su nombre y sus recuerdos. Hasta 5 cambios. Primera versión en menos de 48 horas.", cancion=True),
    Producto("tc-combo", "tc", "Canción + video con fotos", 59_999,
             "La canción y un video con hasta 20 fotos, 3 de ellas restauradas. Video en hasta 72 horas.", 1, 20, cancion=True),
]}

ESTILOS = ["Balada", "Pop", "Cumbia", "Cuarteto", "Folklore", "Rock nacional", "Bolero", "Tango",
           "Reggaetón suave", "Infantil", "Acústico", "Otro"]
VOCES = ["Femenina", "Masculina", "Me da igual"]
DURACIONES = ["Corta (unos 2 minutos)", "Normal (unos 3 minutos)", "Larga (unos 4 minutos)"]


BASE: dict[str, Producto] = dict(PRODUCTOS)     # precios del código; precios.json los pisa


def cargar_precios(ruta: pathlib.Path) -> dict[str, int]:
    """Vuelve a los precios del código y aplica los ajustes guardados (el vigilante de proveedores los escribe)."""
    PRODUCTOS.clear()
    PRODUCTOS.update(BASE)
    try:
        ajustes = json.loads(ruta.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        ajustes = {}
    ajustes = {k: int(v) for k, v in ajustes.items() if k in BASE}
    for k, v in ajustes.items():
        PRODUCTOS[k] = replace(BASE[k], precio=v)
    return ajustes


def guardar_precios(ruta: pathlib.Path, nuevos: dict[str, int]) -> dict[str, int]:
    ajustes = cargar_precios(ruta) | nuevos
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(ajustes, indent=2), encoding="utf-8")
    tmp.replace(ruta)
    return cargar_precios(ruta)


def activos(marca: str | None = None) -> list[dict]:
    return [p.publico() for p in PRODUCTOS.values() if p.activo and (marca is None or p.marca == marca)]
