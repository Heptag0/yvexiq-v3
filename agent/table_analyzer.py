import fdb
import pandas as pd
import anthropic
import os
import re
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
model = "claude-haiku-4-5"

def analizar_tablas(ruta_archivo):
    if ruta_archivo.lower().endswith(".fdb"):
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
            conteo = pd.read_sql(f"SELECT COUNT(*) AS total FROM {tabla}", conn)
            filas = conteo.iloc[0, 0]
            schema += f"- {tabla}: {filas} filas\n"
        conn.close()

        mensaje = client.messages.create(
            model=model,
            max_tokens=256,
            messages=[{"role": "user",
                       "content": f"Eres un experto en bases de datos de negocios. Aquí está un listado de tablas con su número de filas:\n{schema}\nDevuelve ÚNICAMENTE los nombres de las tablas relevantes para analizar ventas y operaciones del negocio, separados por coma. Solo los nombres, sin explicaciones."}]
        )
        respuesta = mensaje.content[0].text
        tablas_encontradas = re.findall(r'\b[A-Z_][A-Z0-9_]+\b', respuesta)
        return ", ".join(tablas_encontradas[:10])