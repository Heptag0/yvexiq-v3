"""
seguridad.py — Utilidades de seguridad para YvexIQ.
Rate limiting en memoria (sin dependencias externas) y validadores de registro.
"""
import re
import time
import threading
from fastapi import HTTPException

# ──────────────────────────────────────────────
#   RATE LIMITING (en memoria del proceso)
# ──────────────────────────────────────────────
# Estructura: { clave: [(timestamp), ...] }
# Se limpia sola descartando timestamps viejos en cada consulta.
_intentos = {}
_lock = threading.Lock()


def _limpiar_viejos(lista, ventana_seg):
    ahora = time.time()
    return [t for t in lista if ahora - t < ventana_seg]


def verificar_rate_limit(clave: str, max_intentos: int, ventana_seg: int, mensaje: str):
    """
    Lanza HTTP 429 si 'clave' supera max_intentos dentro de ventana_seg.
    Registra el intento actual. Thread-safe.
    """
    ahora = time.time()
    with _lock:
        lista = _limpiar_viejos(_intentos.get(clave, []), ventana_seg)
        if len(lista) >= max_intentos:
            # Calcular cuánto falta para poder reintentar
            mas_antiguo = min(lista)
            espera = int(ventana_seg - (ahora - mas_antiguo))
            raise HTTPException(
                status_code=429,
                detail={
                    "codigo": "demasiados_intentos",
                    "mensaje": mensaje,
                    "reintentar_en": max(espera, 1)
                }
            )
        lista.append(ahora)
        _intentos[clave] = lista


def registrar_exito(clave: str):
    """Tras un login exitoso, limpiamos sus intentos fallidos."""
    with _lock:
        _intentos.pop(clave, None)


# Limpieza periódica del diccionario para que no crezca indefinidamente
def _limpieza_global():
    with _lock:
        ahora = time.time()
        # descartar claves cuyos intentos sean todos viejos (> 1 hora)
        muertas = [k for k, v in _intentos.items() if all(ahora - t > 3600 for t in v)]
        for k in muertas:
            _intentos.pop(k, None)


# ──────────────────────────────────────────────
#   VALIDADORES DE REGISTRO
# ──────────────────────────────────────────────
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def obtener_ip(request):
    """
    Obtiene la IP real del cliente detrás de nginx.
    nginx envía X-Forwarded-For; tomamos la primera IP (la del cliente original).
    Si no está, caemos a request.client.host.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # Puede venir "ip_cliente, ip_proxy1, ip_proxy2"; la primera es el cliente
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "desconocida"


def validar_email(email: str):
    email = (email or "").strip()
    if not email or len(email) > 254:
        raise HTTPException(status_code=400, detail={"codigo": "email_invalido", "mensaje": "El correo electrónico no es válido."})
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail={"codigo": "email_invalido", "mensaje": "El correo electrónico no tiene un formato válido."})
    return email.lower()


def validar_password(password: str):
    if not password or len(password) < 8:
        raise HTTPException(status_code=400, detail={"codigo": "password_debil", "mensaje": "La contraseña debe tener al menos 8 caracteres."})
    if len(password) > 128:
        raise HTTPException(status_code=400, detail={"codigo": "password_invalida", "mensaje": "La contraseña es demasiado larga."})
    # Al menos una letra y un número, para evitar contraseñas triviales
    if not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        raise HTTPException(status_code=400, detail={"codigo": "password_debil", "mensaje": "La contraseña debe incluir al menos una letra y un número."})
    return password
