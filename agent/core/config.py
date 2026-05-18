import json
import os
from cryptography.fernet import Fernet
import base64
import hashlib

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".yvexiq", "config.json")

def _get_key():
    machine = os.environ.get("COMPUTERNAME", "yvexiq").encode()
    key = hashlib.sha256(machine).digest()
    return base64.urlsafe_b64encode(key)

def guardar_credenciales(email: str, password: str):
    f = Fernet(_get_key())
    datos = f.encrypt(f"{email}:{password}".encode()).decode()
    guardar_config({"credenciales": datos})

def cargar_credenciales() -> tuple | None:
    config = cargar_config()
    datos = config.get("credenciales")
    if not datos:
        return None
    try:
        f = Fernet(_get_key())
        decrypted = f.decrypt(datos.encode()).decode()
        email, password = decrypted.split(":", 1)
        return email, password
    except:
        return None

def _ensure_dir():
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

def cargar_config() -> dict:
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except:
        return {}

def guardar_config(data: dict):
    _ensure_dir()
    config = cargar_config()
    config.update(data)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

def limpiar_config():
    config = cargar_config()
    config.pop("token", None)
    config.pop("email", None)
    _ensure_dir()
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)