"""
pagos.py — Integración de pagos con Mercado Pago (suscripciones recurrentes).

Enfoque: suscripción SIN plan asociado, con pago pendiente (status="pending").
Estructura según la documentación oficial de Mercado Pago. NO requiere
card_token_id: el cliente completa el pago en el entorno seguro de MP usando el
init_point que devuelve la API. El external_reference (id del usuario) viaja con
la suscripción, permitiendo identificar al usuario de forma DETERMINISTA en el
webhook, sin suponer que el email coincide.

Variables de entorno necesarias (.env):
  MP_ACCESS_TOKEN -> Access Token de producción (APP_USR-...) para cobros reales
  URL_BASE        -> https://yvexiq.com (para back_url)
"""
import os
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")
URL_BASE = os.getenv("URL_BASE", "https://yvexiq.com")
MP_API = "https://api.mercadopago.com"

# Configuración de cada plan: monto (MXN) y frecuencia.
# El monto anual es el total del año.
PLANES = {
    ("basico", "mensual"): {"monto": 199,  "frequency": 1,  "frequency_type": "months", "reason": "YvexIQ Basico Mensual"},
    ("basico", "anual"):   {"monto": 1788, "frequency": 12, "frequency_type": "months", "reason": "YvexIQ Basico Anual"},
    ("pro", "mensual"):    {"monto": 389,  "frequency": 1,  "frequency_type": "months", "reason": "YvexIQ Pro Mensual"},
    ("pro", "anual"):      {"monto": 4188, "frequency": 12, "frequency_type": "months", "reason": "YvexIQ Pro Anual"},
}


def esta_configurado():
    return bool(MP_ACCESS_TOKEN)


def _headers():
    return {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def crear_suscripcion(plan: str, periodo: str, email_usuario: str, referencia: str):
    """
    Crea una suscripción 'pending' y devuelve el link de pago (init_point).
    El cliente completa el pago (y su tarjeta) en Mercado Pago.

    - plan: 'basico' | 'pro'
    - periodo: 'mensual' | 'anual'
    - email_usuario: correo del usuario (payer_email)
    - referencia: id del usuario en la BD (external_reference, para el webhook)

    Devuelve {init_point, preapproval_id, status} o lanza ValueError.
    """
    if not esta_configurado():
        raise ValueError("Mercado Pago no está configurado (falta MP_ACCESS_TOKEN).")

    cfg = PLANES.get((plan, periodo))
    if not cfg:
        raise ValueError(f"No hay configuración para {plan}/{periodo}.")

    payload = {
        "reason": cfg["reason"],
        "external_reference": str(referencia),
        "payer_email": email_usuario,
        "back_url": f"{URL_BASE}/dashboard.html",
        "status": "pending",
        "auto_recurring": {
            "frequency": cfg["frequency"],
            "frequency_type": cfg["frequency_type"],
            "transaction_amount": cfg["monto"],
            "currency_id": "MXN",
        },
    }

    resp = requests.post(
        f"{MP_API}/preapproval",
        json=payload,
        headers=_headers(),
        timeout=20,
    )
    if resp.status_code not in (200, 201):
        raise ValueError(f"Error de Mercado Pago al crear suscripción: {resp.status_code} {resp.text}")

    data = resp.json()
    return {
        "init_point": data.get("init_point"),
        "preapproval_id": data.get("id"),
        "status": data.get("status"),
    }


def consultar_suscripcion(preapproval_id: str):
    """Consulta el estado de una suscripción (status, external_reference, reason, payer_email)."""
    if not MP_ACCESS_TOKEN:
        raise ValueError("Mercado Pago no está configurado.")
    resp = requests.get(
        f"{MP_API}/preapproval/{preapproval_id}",
        headers=_headers(),
        timeout=20,
    )
    if resp.status_code != 200:
        raise ValueError(f"Error al consultar suscripción: {resp.status_code} {resp.text}")
    return resp.json()


def estado_implica_activo(status_mp: str) -> bool:
    """'authorized' = activa y al día. 'pending' = sin pagar aún. 'paused'/'cancelled' = inactiva."""
    return status_mp == "authorized"


def plan_desde_reason(reason: str):
    """Deduce (plan, periodo) del nombre del plan (reason) que devuelve MP."""
    if not reason:
        return (None, None)
    r = reason.lower()
    plan = "pro" if "pro" in r else ("basico" if ("basico" in r or "básico" in r) else None)
    periodo = "anual" if "anual" in r else ("mensual" if "mensual" in r else None)
    return (plan, periodo)


def cancelar_suscripcion(preapproval_id: str):
    """
    Cancela una suscripción en Mercado Pago (status -> cancelled).
    Devuelve True si quedó cancelada, o lanza ValueError si falla.
    """
    if not MP_ACCESS_TOKEN:
        raise ValueError("Mercado Pago no está configurado.")
    resp = requests.put(
        f"{MP_API}/preapproval/{preapproval_id}",
        json={"status": "cancelled"},
        headers=_headers(),
        timeout=20,
    )
    if resp.status_code not in (200, 201):
        raise ValueError(f"Error al cancelar suscripción: {resp.status_code} {resp.text}")
    data = resp.json()
    return data.get("status") == "cancelled"
