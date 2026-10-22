"""Precios terminados en 999 (D-53): pasa los 6 productos de precio fijo a 1 peso menos que el redondo.

  python precios_999.py             muestra los precios de hoy y los nuevos (no cambia nada)
  python precios_999.py --aplicar   los cambia en el servidor (POST /admin/precios)

Los cuadros no se tocan acá: su precio lo calcula el vigilante y hay que cambiarle el redondeo a $…999 (tarea 17, anexo).
Lee TIENDA_ADMIN_TOKEN de claves-tienda.txt (como pedidos.py) y no lo muestra.
"""
import sys

import pedidos

NUEVOS = {"rf-foto-1": 4_999, "rf-pack-5": 14_999, "rf-pack-10": 24_999, "rf-pack-20": 39_999,
          "tc-cancion": 26_999, "tc-combo": 59_999}


def main():
    aplicar = "--aplicar" in sys.argv
    with pedidos.cliente() as c:
        hoy = {p["id"]: p["precio"] for p in c.get("/catalogo").raise_for_status().json()["productos"]}
        for k, v in NUEVOS.items():
            print(f"{k:14} ${hoy.get(k, 0):>7,} → ${v:>7,}".replace(",", "."))
        if not aplicar:
            print("\nNo cambié nada. Para aplicarlo: python precios_999.py --aplicar")
            return
        precios = c.post("/admin/precios", json=NUEVOS).raise_for_status().json()["precios"]
        mal = {k: precios.get(k) for k, v in NUEVOS.items() if precios.get(k) != v}
        print("\nListo: la web ya muestra los precios nuevos." if not mal else f"\nOJO, no quedaron: {mal}")


if __name__ == "__main__":
    main()
