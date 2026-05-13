import pandas as pd
import pandasql as ps
import os
import fdb

def ejecutar_query(sql, ruta_archivo):
    if ruta_archivo.lower().endswith(".csv"):
        df = pd.read_csv(ruta_archivo)
    elif ruta_archivo.lower().endswith(".fdb"):
        conn = fdb.connect(
        host='localhost',
        database=ruta_archivo,
        user='SYSDBA',
        password='masterkey'
        )
        df = pd.read_sql(sql, conn)
        return df.fillna("").to_dict(orient="records")
    else:
        df = pd.read_excel(ruta_archivo)
    resultado = ps.sqldf(sql, {"nombre_tabla": df})
    return resultado.fillna("").to_dict(orient="records")
