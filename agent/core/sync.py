import requests
import os
from core.config import cargar_config
from core.auth import renovar_token

API_URL = "https://yvexiq.com/api"

def _subir_archivo(ruta, archivo, conexion_id, headers):
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
                return "error"
            headers["Authorization"] = f"Bearer {nuevo_token}"
            with open(ruta, "rb") as f:
                res = requests.post(
                    f"{API_URL}/sync",
                    params={"conexion_id": conexion_id},
                    headers=headers,
                    files={"archivo": (archivo, f, "text/csv")}
                )
        return "ok" if res.status_code == 200 else "error"
    except requests.exceptions.ConnectionError:
        return "sin_internet"
    except Exception:
        return "error"

def _obtener_conexiones_servidor(headers) -> set:
    try:
        res = requests.get(f"{API_URL}/conexiones", headers=headers)
        if res.status_code == 200:
            return {str(c["id"]) for c in res.json()}
    except:
        pass
    return set()

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
    csvs = [f for f in os.listdir(carpeta) if f.endswith(".csv")]
    if not csvs:
        return {"ok": False, "error": "No hay archivos para sincronizar"}
    for i, archivo in enumerate(csvs):
        ruta = os.path.join(carpeta, archivo)
        resultado = _subir_archivo(ruta, archivo, conexion_id, headers)
        if resultado == "sin_internet":
            return {"ok": False, "error": "Sin conexión a internet. Verifica tu red e intenta de nuevo."}
        elif resultado == "ok":
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
    token = config.get("token")
    temp_base = os.path.join(os.path.expanduser("~"), ".yvexiq", "temp")
    if not os.path.exists(temp_base):
        return {"ok": False, "error": "No hay datos sincronizados"}
    carpetas = [f for f in os.listdir(temp_base) if os.path.isdir(os.path.join(temp_base, f))]
    if not carpetas:
        return {"ok": False, "error": "No hay conexiones configuradas"}

    headers = {"Authorization": f"Bearer {token}"}
    conexiones_servidor = _obtener_conexiones_servidor(headers)

    # Limpiar carpetas huérfanas
    for carpeta_id in carpetas:
        if carpeta_id not in conexiones_servidor:
            import shutil
            shutil.rmtree(os.path.join(temp_base, carpeta_id), ignore_errors=True)

    carpetas_validas = [f for f in carpetas if f in conexiones_servidor]
    if not carpetas_validas:
        return {"ok": False, "error": "No hay conexiones válidas"}

    # Contar total de archivos para progreso real
    total_csvs = sum(
        len([f for f in os.listdir(os.path.join(temp_base, cid)) if f.endswith(".csv")])
        for cid in carpetas_validas
        if os.path.exists(os.path.join(temp_base, cid))
    )
    archivos_procesados = 0
    total_archivos = 0
    errores = []

    for carpeta_id in carpetas_validas:
        try:
            conexion_id = int(carpeta_id)
        except:
            continue
        carpeta = os.path.join(temp_base, carpeta_id)

        def progreso_archivo(p, cid=conexion_id):
            nonlocal archivos_procesados
            if p == 100:
                archivos_procesados += 1
                if callback and total_csvs > 0:
                    callback(int(archivos_procesados / total_csvs * 100))

        resultado = sincronizar(conexion_id, carpeta, callback=progreso_archivo)
        if resultado["ok"]:
            total_archivos += resultado["archivos"]
        else:
            errores.append(f"Conexión {conexion_id}: {resultado['error']}")
            # Si es problema de internet, parar inmediatamente
            if "internet" in resultado["error"].lower():
                return {"ok": False, "error": resultado["error"]}

    if callback:
        callback(100)

    if errores and total_archivos == 0:
        return {"ok": False, "error": "\n".join(errores)}
    return {"ok": True, "archivos": total_archivos}

def re_extraer_y_sincronizar(conexion: dict, callback=None) -> dict:
    from extractor import extraer_tablas
    from table_analyzer import analizar_tablas
    
    conexion_id = conexion["id"]
    ruta_archivo = conexion.get("ruta_archivo", "")
    
    if not ruta_archivo or not os.path.exists(ruta_archivo):
        carpeta = os.path.join(os.path.expanduser("~"), ".yvexiq", "temp", str(conexion_id))
        if os.path.exists(carpeta):
            return sincronizar(conexion_id, carpeta, callback)
        return {"ok": False, "error": "Archivo original no encontrado"}
    
    try:
        tablas = analizar_tablas(ruta_archivo) if ruta_archivo.lower().endswith(".fdb") else None
        carpeta = extraer_tablas(ruta_archivo, tablas, conexion_id)
        return sincronizar(conexion_id, carpeta, callback)
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": "Sin conexión a internet. Verifica tu red e intenta de nuevo."}
    except Exception as e:
        return {"ok": False, "error": str(e)}