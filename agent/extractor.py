import pandas as pd
import fdb
import os
from dotenv import load_dotenv
load_dotenv('C:/Users/hepta/Desktop/YvexIQ-V3/backend/.env')

def extraer_tablas(ruta_archivo, tablas_relevantes, conexion_id):
    carpeta = os.path.join(os.path.expanduser("~"), ".yvexiq", "temp", str(conexion_id))
    
    if os.path.exists(carpeta):
        import shutil
        shutil.rmtree(carpeta)
    os.makedirs(carpeta, exist_ok=True)

    if ruta_archivo.lower().endswith(".csv"):
        import shutil
        nombre = os.path.basename(ruta_archivo)
        shutil.copy(ruta_archivo, os.path.join(carpeta, nombre))
        return carpeta

    if ruta_archivo.lower().endswith(".xlsx"):
        df = pd.read_excel(ruta_archivo)
        nombre = os.path.basename(ruta_archivo).replace(".xlsx", ".csv")
        df.to_csv(os.path.join(carpeta, nombre), index=False)
        return carpeta

    split = tablas_relevantes.split(", ")
    for tabla in split:
        conn = fdb.connect(
            host=os.getenv('FIREBIRD_HOST'),
            database=ruta_archivo,
            user=os.getenv('FIREBIRD_USER'),
            password=os.getenv('FIREBIRD_PASSWORD')
        )
        df = pd.read_sql(f"SELECT * FROM {tabla}", conn)
        df.to_csv(os.path.join(carpeta, f"{tabla}.csv"), index=False)

    return carpeta