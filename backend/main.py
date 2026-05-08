from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import engine, Base
from models import Usuario
from schemas import UsuarioCreate
from database import get_db
import auth

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


@app.post("/register")
def register_user(user: UsuarioCreate, db: Session = Depends(get_db)):
    existing_user = db.query(Usuario).filter(Usuario.email == user.email).first()
    if existing_user is not None:
        raise HTTPException(status_code=400, detail="El correo ya esta registrado")
    user.password = auth.hash_password(user.password)
    db_user = Usuario(email=user.email, password=user.password)
    db.add(db_user)
    db.commit()
    return {"message": "Usuario registrado exitosamente"}
