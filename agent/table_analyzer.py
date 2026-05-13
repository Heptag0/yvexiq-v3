import fdb
import pandas as pd
import anthropic
import os
from dotenv import load_dotenv

load_dotenv('C:/Users/hepta/Desktop/YvexIQ-V3/backend/.env')
client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
model = "claude-haiku-4-5"

def analizar_tablas(ruta_archivo):
    if ruta_archivo.lower().endswith(".fdb"):
        conn = fdb.connect(
            host='localhost',
            database=ruta_archivo,
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
        mensaje =client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user",
                       "content": f"Eres un experto en base de datos de negocios. Aqui esta un listado de tablas con su numero de filas {schema}. Dime cuales son relevantes para analizar las ventas y operaciones del negocio. Responde solo con los nombres de las tablas separados por coma."}]
        )
        return mensaje.content[0].text
        
    