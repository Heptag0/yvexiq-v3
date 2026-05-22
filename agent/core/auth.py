import requests
from core.config import cargar_config, guardar_config, limpiar_config
from core.config import cargar_config, guardar_config, limpiar_config, guardar_credenciales


API_URL = "https://yvexiq.com"  

def login(email: str, password: str) -> dict:
    try:
        res = requests.post(
            f"{API_URL}/login",
            data={"username": email, "password": password}
        )
        if res.status_code == 200:
            data = res.json()
            guardar_config({
                "token": data["access_token"],
                "email": email
            })
            guardar_credenciales(email, password)
            return {"ok": True}
        else:
            return {"ok": False, "error": res.json().get("detail", "Error al iniciar sesión")}
    except:
        return {"ok": False, "error": "No se pudo conectar con el servidor"}

def logout():
    try:
        token = cargar_config().get("token")
        if token:
            requests.post(
                f"{API_URL}/logout",
                headers={"Authorization": f"Bearer {token}"}
            )
    except:
        pass
    limpiar_config()

def get_token() -> str | None:
    return cargar_config().get("token")

def renovar_token() -> str | None:
    from core.config import cargar_credenciales
    credenciales = cargar_credenciales()
    if not credenciales:
        return None
    email, password = credenciales
    resultado = login(email, password)
    if resultado["ok"]:
        return cargar_config().get("token")
    return None

def esta_autenticado() -> bool:
    return get_token() is not None
