from fastapi import FastAPI
from database import engine, Base
from models import Usuario

# Crear tabla en la base de datos
Base.metadata.create_all(bind=engine)

app = FastAPI()
@app.get("/")

def root():
    return {"mensaje": "YvexIQ API funcionando"}


try:
    with engine.connect() as conn:
        print("Conexion exitosa a la base de datos")
except Exception as e:
    print("Error al conectar a la base de datos:", e)
