import pandas as pd
import pandasql as ps
import os
import fdb

def ejecutar_query(sql, ruta_archivo):
    if ruta_archivo.lower().endswith(".csv"):
        df = pd.read_csv(ruta_archivo)
    elif ruta_archivo.lower().endswith(".fdb"):
        conn = fdb.connect(
            host=os.getenv('FIREBIRD_HOST'),
            database=ruta_archivo,
            user=os.getenv('FIREBIRD_USER'),
            password=os.getenv('FIREBIRD_PASSWORD')
        )

        df = pd.read_sql(sql, conn)
        return df.fillna("").to_dict(orient="records")
    else:
        df = pd.read_excel(ruta_archivo)
    resultado = ps.sqldf(sql, {"nombre_tabla": df})
    return resultado.fillna("").to_dict(orient="records")



def ejecutar_query_sync(sql, carpeta):
    tablas = {}
    for archivo in os.listdir(carpeta):
        if archivo.lower().endswith(".csv"):
            nombre_tabla = archivo.replace(".csv", "")
            tablas[nombre_tabla] = pd.read_csv(os.path.join(carpeta, archivo))
    resultado = ps.sqldf(sql, tablas)
    return resultado.fillna("").to_dict(orient="records")   