import pandas as pd
import pandasql as ps
import os

def ejecutar_query(sql, ruta_archivo):
    if ruta_archivo.endswith(".csv"):
        df = pd.read_csv(ruta_archivo)
    else:
        df = pd.read_excel(ruta_archivo)
    resultado = ps.sqldf(sql, {"nombre_tabla": df})
    return resultado.to_dict(orient="records")
