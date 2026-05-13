import pandas as pd
import fdb
import os

def extraer_tablas(ruta_archivo, tablas_relevantes):
    split = tablas_relevantes.split(", ")
    os.makedirs("temp", exist_ok=True)
    for tabla in split:
        conn = fdb.connect(
            host='localhost',
            database=ruta_archivo,
            user='SYSDBA',
            password='masterkey'
        )
        df = pd.read_sql(f"SELECT * FROM {tabla}", conn)
        df.to_csv(f"temp/{tabla}.csv", index=False)
                  
