from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import engine, Base
from models import Usuario
from schemas import UsuarioCreate, UsuarioLogin
from database import get_db
import auth
from llm import generate_sql


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




@app.post("/login")
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    db_user = db.query(Usuario).filter(Usuario.email == form_data.username).first()
    if db_user is None:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    if not auth.verify_password(form_data.password, db_user.password):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    access_token = auth.create_access_token(data={"sub": form_data.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/generar_sql")
def test_sql():
    schema = "CREATE TABLE clientes (id SERIAL PRIMARY KEY, nombre VARCHAR(255), apellido VARCHAR(255), email VARCHAR(255)); " \
    "CREATE TABLE ventas (id SERIAL PRIMARY KEY, id_cliente INT, fecha DATE, monto DECIMAL(10,2)); "
    sql = generate_sql("¿Cuantos clientes hay?", schema)
    return {"sql": sql}