import requests
import os
from core.config import cargar_config
from core.auth import renovar_token

API_URL = "https://yvexiq.com/api"

def _subir_archivo(ruta, archivo, conexion_id, headers) -> bool:
    try:
        with open(ruta, "rb") as f:
            res = requests.post(
                f"{API_URL}/sync",
                params={"conexion_id": conexion_id},
                headers=headers,
                files={"archivo": (archivo, f, "text/csv")}
            )
        if res.status_code == 401:
            nuevo_token = renovar_token()
            if not nuevo_token:
                return False
            headers["Authorization"] = f"Bearer {nuevo_token}"
            with open(ruta, "rb") as f:
                res = requests.post(
                    f"{API_URL}/sync",
                    params={"conexion_id": conexion_id},
                    headers=headers,
                    files={"archivo": (archivo, f, "text/csv")}
                )
        return res.status_code == 200
    except Exception as e:
        print(f"Error subiendo {archivo}: {e}")
        return False

def sincronizar(conexion_id, carpeta, callback=None) -> dict:
    config = cargar_config()
    token = config.get("token")

    if not all([token, conexion_id, carpeta]):
        return {"ok": False, "error": "Agente no configurado correctamente"}

    if not os.path.exists(carpeta):
        return {"ok": False, "error": "Carpeta de datos no encontrada"}

    headers = {"Authorization": f"Bearer {token}"}
    archivos_subidos = 0
    errores = []

    csvs = [f for f in os.listdir(carpeta) if f.endswith((".csv", ".xlsx"))]
    if not csvs:
        return {"ok": False, "error": "No hay archivos para sincronizar"}

    for i, archivo in enumerate(csvs):
        ruta = os.path.join(carpeta, archivo)
        if _subir_archivo(ruta, archivo, conexion_id, headers):
            archivos_subidos += 1
        else:
            errores.append(archivo)

        if callback:
            callback(int((i + 1) / len(csvs) * 100))

    if errores:
        return {"ok": False, "error": f"Fallaron: {', '.join(errores)}"}
    return {"ok": True, "archivos": archivos_subidos}

def sincronizar_todas(callback=None) -> dict:
    config = cargar_config()
    temp_base = os.path.join(os.path.expanduser("~"), ".yvexiq", "temp")

    if not os.path.exists(temp_base):
        return {"ok": False, "error": "No hay datos sincronizados"}

    carpetas = [f for f in os.listdir(temp_base) if os.path.isdir(os.path.join(temp_base, f))]
    if not carpetas:
        return {"ok": False, "error": "No hay conexiones configuradas"}

    total_archivos = 0
    errores = []

    for idx, carpeta_id in enumerate(carpetas):
        try:
            conexion_id = int(carpeta_id)
        except:
            continue
        carpeta = os.path.join(temp_base, carpeta_id)
        resultado = sincronizar(conexion_id, carpeta)
        if resultado["ok"]:
            total_archivos += resultado["archivos"]
        else:
            errores.append(f"Conexión {conexion_id}: {resultado['error']}")

        if callback:
            callback(int((idx + 1) / len(carpetas) * 100))

    if errores and total_archivos == 0:
        return {"ok": False, "error": "\n".join(errores)}
    return {"ok": True, "archivos": total_archivos}
