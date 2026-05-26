import pandas as pd
import fdb
import os
import re
import shutil
import sys
import tempfile

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

def extraer_tablas(ruta_archivo, tablas_relevantes, conexion_id):
    carpeta = os.path.join(os.path.expanduser("~"), ".yvexiq", "temp", str(conexion_id))
    if os.path.exists(carpeta):
        shutil.rmtree(carpeta)
    os.makedirs(carpeta, exist_ok=True)

    if ruta_archivo.lower().endswith(".csv"):
        nombre = os.path.basename(ruta_archivo)
        shutil.copy(ruta_archivo, os.path.join(carpeta, nombre))
        return carpeta

    if ruta_archivo.lower().endswith(".xlsx"):
        xl = pd.ExcelFile(ruta_archivo)
        for hoja in xl.sheet_names:
            df = xl.parse(hoja)
            df.to_csv(os.path.join(carpeta, hoja + ".csv"), index=False)
        return carpeta

    # Firebird — copiar a temp para no bloquear el archivo original
    _cargar_firebird()
    temp_dir = tempfile.mkdtemp()
    temp_fdb = os.path.join(temp_dir, os.path.basename(ruta_archivo))
    shutil.copy2(ruta_archivo, temp_fdb)
    try:
        tablas = re.split(r'[,]\s*', tablas_relevantes)
        conn = fdb.connect(
            database=temp_fdb,
            user='SYSDBA',
            password='masterkey'
        )
        for tabla in tablas:
            tabla = tabla.strip()
            if tabla:
                df = pd.read_sql(f"SELECT * FROM {tabla}", conn)
                df.to_csv(os.path.join(carpeta, f"{tabla}.csv"), index=False)
        conn.close()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return carpeta