import pandas as pd
import fdb
import os
import re
import shutil
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

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
            nombre = hoja + ".csv"
            df.to_csv(os.path.join(carpeta, nombre), index=False)
        return carpeta

    # Firebird — una sola conexión para todas las tablas
    tablas = re.split(r'[,]\s*', tablas_relevantes)
    conn = fdb.connect(
        host=os.getenv('FIREBIRD_HOST'),
        database=ruta_archivo,
        user=os.getenv('FIREBIRD_USER'),
        password=os.getenv('FIREBIRD_PASSWORD')
    )
    for tabla in tablas:
        tabla = tabla.strip()
        if tabla:
            df = pd.read_sql(f"SELECT * FROM {tabla}", conn)
            df.to_csv(os.path.join(carpeta, f"{tabla}.csv"), index=False)
    conn.close()

    return carpeta