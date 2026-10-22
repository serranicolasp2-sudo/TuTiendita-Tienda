"""Cobros reales de Mercado Pago de los pedidos de la tienda, y la comisión real que se desprende de ellos.

Lo usan /admin/pagos (la pantalla Plata de la centralita) y el vigilante (precio de los cuadros, D-49): la comisión de
MP sale de lo que MP cobró de verdad en las ventas, nunca de un porcentaje fijo.
"""
import re
import time
from datetime import datetime, timedelta, timezone

from . import mp

CACHE = 600                 # segundos que vale la lectura de un pago que todavía no se liberó
DIAS_COMISION = 180         # la comisión real se calcula con los cobros de los últimos 180 días


class Pagos:
    def __init__(self, cfg, base, obtener_pago=None):
        self.cfg, self.base = cfg, base
        self.obtener_pago = obtener_pago or (lambda pago_id: mp.obtener_pago(cfg, pago_id))
        self.cache: dict[str, tuple[float, dict]] = {}

    def _leer(self, p: dict) -> dict:
        """Lista blanca de campos del pago (nada del pagador). Si MP falla, el pedido viene con "error"."""
        pago_id = str(p["mp_pago"])
        if pago_id in self.cache:
            cuando, datos = self.cache[pago_id]
            if datos["liberacion"]["estado"] == "released" or time.time() - cuando < CACHE:
                return datos
        try:
            r = self.obtener_pago(pago_id)
        except Exception as e:
            error = re.sub(r"APP_USR-[A-Za-z0-9_-]+", "[TOKEN]", str(e))
            error = re.sub(r"Bearer\s+[A-Za-z0-9_-]+", "Bearer [TOKEN]", error)
            return {"pedido": p["id"], "producto": p.get("producto"), "precio": int(p.get("precio") or 0),
                    "pago": pago_id, "error": error[:200]}
        monto = float(r.get("transaction_amount") or 0.0)
        comisiones = [{"tipo": f.get("type"), "monto": float(f.get("amount") or 0.0), "a_cargo": f.get("fee_payer")}
                      for f in (r.get("fee_details") or [])]
        neto = (r.get("transaction_details") or {}).get("net_received_amount")
        datos = {
            "pedido": p["id"], "producto": p.get("producto"), "precio": int(p.get("precio") or 0), "pago": pago_id,
            "estado": r.get("status"), "detalle": r.get("status_detail"),
            "medio": r.get("payment_method_id"), "tipo_medio": r.get("payment_type_id"), "cuotas": r.get("installments"),
            "monto": monto, "comisiones": comisiones,
            "neto": float(neto) if neto is not None else round(monto - sum(c["monto"] for c in comisiones), 2),
            "reembolsado": float(r.get("transaction_amount_refunded") or 0.0),
            "liberacion": {"fecha": r.get("money_release_date"), "estado": r.get("money_release_status")},
            "aprobado": r.get("date_approved"),
        }
        self.cache[pago_id] = (time.time(), datos)
        return datos

    def lista(self, desde: str | None = None) -> list[dict]:
        pedidos = [p for p in self.base.listar(limite=500) if p.get("mp_pago")]
        if desde:
            pedidos = [p for p in pedidos if p.get("pagado") and p["pagado"][:10] >= desde[:10]]
        return [self._leer(p) for p in pedidos]

    def comision_real(self) -> dict | None:
        """Lo que MP se llevó de verdad: suma de comisiones a cargo de la tienda / suma de lo cobrado, en los cobros
        aprobados de los últimos 180 días (sin reembolsos ni lecturas con error). None si todavía no hay ninguno."""
        desde = (datetime.now(timezone.utc) - timedelta(days=DIAS_COMISION)).strftime("%Y-%m-%d")
        validos = [x for x in self.lista(desde) if not x.get("error") and x.get("estado") == "approved"
                   and not x.get("reembolsado") and x.get("monto")]
        if not validos:
            return None
        por_medio: dict[str, dict] = {}
        for x in validos:
            m = por_medio.setdefault(x.get("tipo_medio") or "otro", {"pagos": 0, "monto": 0.0, "comisiones": 0.0})
            m["pagos"] += 1
            m["monto"] += x["monto"]
            m["comisiones"] += sum(c["monto"] for c in x["comisiones"] if c.get("a_cargo") in (None, "collector"))
        monto = sum(m["monto"] for m in por_medio.values())
        comisiones = sum(m["comisiones"] for m in por_medio.values())
        fechas = sorted(x["aprobado"][:10] for x in validos if x.get("aprobado"))
        return {
            "tasa": comisiones / monto,
            "porcentaje": round(comisiones / monto * 100, 2),
            "pagos": len(validos),
            "por_medio": {k: {"pagos": v["pagos"], "porcentaje": round(v["comisiones"] / v["monto"] * 100, 2)}
                          for k, v in por_medio.items()},
            "desde": fechas[0] if fechas else None,
            "hasta": fechas[-1] if fechas else None,
            "leido": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "fuente": "API de Mercado Pago: comisiones de tus cobros reales",
        }
