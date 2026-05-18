import pandas as pd
import pandasql as ps
import fdb
import os

def detectar_schema(ruta_archivo):
    if ruta_archivo.lower().endswith(".csv"):
        df = pd.read_csv(ruta_archivo)
    elif ruta_archivo.lower().endswith(".fdb"):
        conn = fdb.connect(
            host=os.getenv('FIREBIRD_HOST'),
            database=ruta_archivo,
            user=os.getenv('FIREBIRD_USER'),
            password=os.getenv('FIREBIRD_PASSWORD')
        )

        tablas = pd.read_sql("SELECT RDB$RELATION_NAME FROM RDB$RELATIONS WHERE RDB$SYSTEM_FLAG = 0 AND RDB$VIEW_BLR IS NULL", conn)
        schema = "Tablas disponibles:\n"
        for tabla in tablas["RDB$RELATION_NAME"]:
            tabla = tabla.strip()
            columnas = pd.read_sql(f"SELECT RDB$FIELD_NAME FROM RDB$RELATION_FIELDS WHERE RDB$RELATION_NAME = '{tabla}'", conn)
            schema += f"\nTabla: {tabla}\nColumnas:\n"
            for columna in columnas["RDB$FIELD_NAME"]:
                columna = columna.strip()
                try:
                    ejemplos_df = pd.read_sql(f"SELECT FIRST 3 {columna} FROM {tabla}", conn)
                    ejemplos = ejemplos_df[columna].dropna().unique().tolist()
                except:
                    ejemplos = []
            schema += f"- {columna} (ejemplos: {ejemplos})\n"
        return schema
    else:
        df = pd.read_excel(ruta_archivo)
    schema = "Tabla: nombre_tabla\nColumnas:\n"
    for columna, tipo in df.dtypes.items():
        ejemplos = df[columna].dropna().unique()[:3].tolist()
        schema += f"- {columna} ({tipo}, ejemplos: {ejemplos})\n"
    return schema


def detectar_schema_sync(carpeta):
    schema = ""
    for archivo in os.listdir(carpeta):
        if archivo.lower().endswith(".csv"):
            df = pd.read_csv(os.path.join(carpeta, archivo))
            nombre_tabla = archivo.replace(".csv", "")
            schema += f"Tabla: {nombre_tabla}\nColumnas:\n"
            for columna in df.columns:
                ejemplos = df[columna].dropna().unique()[:3].tolist()
                schema += f"- {columna} (ejemplos: {ejemplos})\n"
    return schema
        
