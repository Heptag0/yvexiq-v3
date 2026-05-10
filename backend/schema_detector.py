import pandas as pd
import pandasql as ps

def detectar_schema(ruta_archivo):
    if ruta_archivo.endswith(".csv"):
        df = pd.read_csv(ruta_archivo)
    else:
        df = pd.read_excel(ruta_archivo)
    schema = "Tabla: nombre_tabla\nColumnas:\n"
    for columna, tipo in df.dtypes.items():
        ejemplos = df[columna].dropna().unique()[:3].tolist()
        schema += f"- {columna} ({tipo}, ejemplos: {ejemplos})\n"
    return schema
