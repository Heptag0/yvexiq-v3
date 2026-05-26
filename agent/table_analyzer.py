import fdb
import pandas as pd
import requests
import os
import re
import sys
import shutil
import tempfile
from core.config import cargar_config

API_URL = "https://yvexiq.com/api"

def _cargar_firebird():
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    
    dll_local = os.path.join(base, 'fbembed.dll')
    if os.path.exists(dll_local):
        fdb.load_api(dll_local)
        return
    
    raise RuntimeError(f"No se encontró fbembed.dll en {base}. Reinstala el agente.")

def analizar_tablas(ruta_archivo):
    token = cargar_config().get("token")
    headers = {"Authorization": f"Bearer {token}"}
    
    if ruta_archivo.lower().endswith(".fdb"):
        _cargar_firebird()
        temp_dir = tempfile.mkdtemp()
        temp_fdb = os.path.join(temp_dir, os.path.basename(ruta_archivo))
        shutil.copy2(ruta_archivo, temp_fdb)
        try:
            conn = fdb.connect(
                database=temp_fdb,
                user='SYSDBA',
                password='masterkey'
            )
            tablas = pd.read_sql("SELECT RDB$RELATION_NAME FROM RDB$RELATIONS WHERE RDB$SYSTEM_FLAG = 0 AND RDB$VIEW_BLR IS NULL", conn)
            schema = "Tablas disponibles:\n"
            for tabla in tablas["RDB$RELATION_NAME"]:
                tabla = tabla.strip()
                conteo = pd.read_sql(f"SELECT COUNT(*) AS total FROM {tabla}", conn)
                filas = conteo.iloc[0, 0]
                schema += f"- {tabla}: {filas} filas\n"
            conn.close()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    else:
        df = pd.read_csv(ruta_archivo) if ruta_archivo.endswith(".csv") else pd.read_excel(ruta_archivo)
        schema = f"Tabla: {os.path.basename(ruta_archivo)}\nColumnas: {', '.join(df.columns)}\nFilas: {len(df)}\n"

    res = requests.post(
        f"{API_URL}/analizar-schema",
        json={"schema": schema},
        headers=headers
    )
    
    if res.status_code == 200:
        respuesta = res.json().get("tablas", "")
        tablas_encontradas = re.findall(r'\b[A-Z_][A-Z0-9_]+\b', respuesta)
        return ", ".join(tablas_encontradas[:10]) if tablas_encontradas else os.path.basename(ruta_archivo)
    else:
        return os.path.basename(ruta_archivo)