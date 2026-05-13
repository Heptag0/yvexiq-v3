import requests
import os

def subir_archivo(archivo, token, url, conexion_id):
    headers = {"Authorization": f"Bearer {token}"}
    with open(archivo, "rb") as f:
        files = {"archivo": f}
        response = requests.post(f"{url}/sync?conexion_id={conexion_id}", headers=headers, files=files)
        return response

def sincronizar_todo(token, url, conexion_id):
    archivos = os.listdir("temp/")
    for archivo in archivos:
        if archivo.endswith(".csv"):
            ruta_completa = os.path.join("temp/", archivo)
            respuesta = subir_archivo(ruta_completa, token, url, conexion_id)
            print(f"{archivo}: {respuesta.status_code}")
