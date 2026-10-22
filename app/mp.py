"""Mercado Pago: Checkout Pro (API de Preferences), consulta de pagos y verificación de la firma del webhook."""
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import httpx

API = "https://api.mercadopago.com"


class ErrorMP(Exception):
    pass


def _cliente(token: str) -> httpx.Client:
    return httpx.Client(base_url=API, timeout=20, headers={"Authorization": f"Bearer {token}"})


def crear_preferencia(cfg, pedido: dict, producto) -> dict:
    web = cfg.url_web(pedido["marca"])
    vence = datetime.now(timezone(timedelta(hours=-3))) + timedelta(days=2)
    cuerpo = {
        "items": [{
            "id": producto.id,
            "title": producto.nombre,
            "description": f"Pedido {pedido['id']}",
            "quantity": 1,
            "unit_price": float(pedido["precio"]),
            "currency_id": "ARS",
        }],
        "payer": {"name": pedido["nombre"], "email": pedido["email"]},
        "external_reference": pedido["id"],
        "metadata": {"pedido": pedido["id"]},
        "back_urls": {
            "success": f"{web}/gracias.html?pedido={pedido['id']}",
            "pending": f"{web}/gracias.html?pedido={pedido['id']}",
            "failure": f"{web}/gracias.html?pedido={pedido['id']}&pago=fallido",
        },
        "statement_descriptor": "TU CANCION" if pedido["marca"] == "tc" else "RESTAURACION FOTOS",
        "expires": True,
        "expiration_date_to": vence.isoformat(timespec="milliseconds"),
    }
    if web.startswith("https://"):
        cuerpo["auto_return"] = "approved"     # Mercado Pago solo acepta direcciones https públicas
    if cfg.url_webhook.startswith("https://"):
        cuerpo["notification_url"] = cfg.url_webhook
    with _cliente(cfg.mp_access_token) as c:
        r = c.post("/checkout/preferences", json=cuerpo, headers={"X-Idempotency-Key": f"pref-{pedido['id']}"})
    if r.status_code >= 300:
        raise ErrorMP(f"Mercado Pago {r.status_code}: {r.text[:300]}")
    return r.json()


def obtener_pago(cfg, pago_id: str) -> dict:
    with _cliente(cfg.mp_access_token) as c:
        r = c.get(f"/v1/payments/{pago_id}")
    if r.status_code >= 300:
        raise ErrorMP(f"Mercado Pago {r.status_code}: {r.text[:300]}")
    return r.json()


def pagos_de_pedido(cfg, pedido_id: str) -> list[dict]:
    with _cliente(cfg.mp_access_token) as c:
        r = c.get("/v1/payments/search", params={"external_reference": pedido_id,
                                                 "sort": "date_created", "criteria": "desc"})
    if r.status_code >= 300:
        raise ErrorMP(f"Mercado Pago {r.status_code}: {r.text[:300]}")
    return r.json().get("results", [])


def firma_valida(secreto: str, x_signature: str | None, x_request_id: str | None, data_id: str | None) -> bool:
    """Valida el encabezado x-signature (ts=…,v1=…) según la documentación de webhooks de Mercado Pago."""
    if not secreto or not x_signature:
        return False
    partes = dict(p.strip().split("=", 1) for p in x_signature.split(",") if "=" in p)
    ts, v1 = partes.get("ts"), partes.get("v1")
    if not ts or not v1:
        return False
    manifiesto = ""
    if data_id:
        manifiesto += f"id:{data_id.lower() if data_id.isalnum() else data_id};"
    if x_request_id:
        manifiesto += f"request-id:{x_request_id};"
    manifiesto += f"ts:{ts};"
    esperado = hmac.new(secreto.encode(), manifiesto.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)


def pago_corresponde(pago: dict, pedido: dict) -> bool:
    """El pago tiene que estar aprobado, ser de este pedido y por el monto exacto, en pesos."""
    return (pago.get("status") == "approved"
            and pago.get("external_reference") == pedido["id"]
            and pago.get("currency_id") == "ARS"
            and abs(float(pago.get("transaction_amount") or 0) - float(pedido["precio"])) < 0.01)
