from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import engine, Base
from models import Usuario, Conexion, Historial
from schemas import UsuarioCreate, UsuarioLogin, Consulta, ConexionCreate, ConexionResponse, HistorialResponse
from database import get_db
import auth
from llm import generate_sql, generate_explanation, generate_chart, generate_fallback
from query_executor import ejecutar_query, ejecutar_query_sync
from schema_detector import detectar_schema, detectar_schema_sync
import os
from datetime import datetime
from limits import verificar_limite_consultas, verificar_limite_conexiones

# Crear tabla en la base de datos
Base.metadata.create_all(bind=engine)

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    db_user = Usuario(
        email=user.email, 
        password=user.password,
        tipo_suscripcion="gratuito",
        suscripcion_activa=True,
        fecha_registro=datetime.now(),
            )
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
    refresh_token = auth.create_refresh_token(data={"sub": form_data.username})
    
    db_user.refresh_token = refresh_token
    db.commit()

    response = JSONResponse(content={
        "access_token": access_token,
        "token_type": "bearer",
        "es_admin": db_user.es_admin or False
    })
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 24 * 7
    )
    return response

@app.post("/generar_sql")
def test_sql():
    schema = "CREATE TABLE clientes (id SERIAL PRIMARY KEY, nombre VARCHAR(255), apellido VARCHAR(255), email VARCHAR(255)); " \
    "CREATE TABLE ventas (id SERIAL PRIMARY KEY, id_cliente INT, fecha DATE, monto DECIMAL(10,2)); "
    sql = generate_sql("¿Cuantos clientes hay?", schema)
    return {"sql": sql}

@app.post("/consultar")
def consultar(consulta: Consulta, current_user: Usuario = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    verificar_limite_consultas(current_user, db)
    conexion_id = consulta.conexion_id
    db_conexion = db.query(Conexion).filter(Conexion.id == conexion_id).first()
    if db_conexion is None:
        raise HTTPException(status_code=404, detail="Conexion no encontrada")
    if db_conexion.usuario_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para acceder a esta conexion")
    carpeta = f"data/{current_user.id}/{conexion_id}"
    if not os.path.exists(carpeta):
        return {"error": "Esta conexión no tiene datos sincronizados. Ejecuta el agente para sincronizar."}
    schema = detectar_schema_sync(carpeta)
    sql = generate_sql(consulta.pregunta, schema, "csv")
    if sql.strip() == "NO_DATA":
        respuesta = generate_fallback(consulta.pregunta, schema, "Pregunta no relacionada con los datos")
        return {"explicacion": respuesta, "resultados": [], "graficos": None}
    try:
        resultados = ejecutar_query_sync(sql, carpeta)

        if consulta.modo == "rapido":
            db_historial = Historial(
                usuario_id=current_user.id,
                conexion_id=conexion_id,
                pregunta=consulta.pregunta,
                respuesta=str(resultados),
                fecha=datetime.utcnow()
            )
            db.add(db_historial)
            db.commit()
            return {
                "resultados": resultados,
                "explicacion": None,
                "graficos": None
            }

        respuesta_natural = generate_explanation(consulta.pregunta, sql, resultados)
        graficos = generate_chart(consulta.pregunta, resultados)
        db_historial = Historial(
            usuario_id=current_user.id,
            conexion_id=conexion_id,
            pregunta=consulta.pregunta,
            respuesta=respuesta_natural,
            fecha=datetime.utcnow()
        )
        db.add(db_historial)
        db.commit()
        print(f"Historial guardado: {db_historial.id}")
        return {
            "resultados": resultados,
            "explicacion": respuesta_natural,
            "graficos": graficos
        }
    except Exception as e:
        fallback = generate_fallback(consulta.pregunta, schema, str(e))
        return {"error": fallback}

@app.post("/sync")
def sincronizar(conexion_id: int, current_user: Usuario = Depends(auth.get_current_user), db: Session = Depends(get_db), archivo: UploadFile = File(...)):
    db_conexion = db.query(Conexion).filter(Conexion.id == conexion_id).first()
    if db_conexion is None:
        raise HTTPException(status_code=404, detail="Conexion no encontrada")
    if db_conexion.usuario_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para acceder a esta conexion")
    contenido = archivo.file.read()
    carpeta = f"data/{current_user.id}/{conexion_id}"
    os.makedirs(carpeta, exist_ok=True)
    ruta_destino = os.path.join(carpeta, archivo.filename)
    with open(ruta_destino, "wb") as f:
        f.write(contenido)
    db_conexion.fecha_ultima_sincronizacion = datetime.utcnow()
    db.commit()
    return {"message": "Archivo sincronizado exitosamente"}

@app.get("/conexiones", response_model=list[ConexionResponse])
def listar_conexiones(current_user: Usuario = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    conexiones = db.query(Conexion).filter(Conexion.usuario_id == current_user.id).all()
    return conexiones

@app.post("/conexiones", response_model=ConexionResponse)   
def crear_conexion(conexion: ConexionCreate, current_user: Usuario = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    verificar_limite_conexiones(current_user, db)
    db_conexion = Conexion(**conexion.dict(), usuario_id=current_user.id)
    db.add(db_conexion)
    db.commit()
    return db_conexion

@app.delete("/conexiones/{id}")
def eliminar_conexion(id: int, current_user: Usuario = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    db_conexion = db.query(Conexion).filter(Conexion.id == id).first()
    if db_conexion is None:
        raise HTTPException(status_code=404, detail="Conexion no encontrada")
    if db_conexion.usuario_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para acceder a esta conexion")
    db.delete(db_conexion)
    db.commit()
    return {"message": "Conexion eliminada exitosamente"}

@app.get("/historial", response_model=list[HistorialResponse])
def obtener_historial(current_user: Usuario = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    historial = db.query(Historial).filter(
        Historial.usuario_id == current_user.id
    ).order_by(Historial.fecha.desc()).limit(10).all()
    return historial

@app.post("/refresh")
def refresh_token(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No hay refresh token")
    
    payload = auth.verify_refresh_token(token)
    email = payload.get("sub")
    
    db_user = db.query(Usuario).filter(Usuario.email == email).first()
    if db_user is None or db_user.refresh_token != token:
        raise HTTPException(status_code=401, detail="Refresh token invalido")
    
    new_access_token = auth.create_access_token(data={"sub": email})
    return {"access_token": new_access_token, "token_type": "bearer"}

@app.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if token:
        db_user = db.query(Usuario).filter(Usuario.refresh_token == token).first()
        if db_user:
            db_user.refresh_token = None
            db.commit()
    
    response = JSONResponse(content={"message": "Sesión cerrada"})
    response.delete_cookie("refresh_token")
    return response


@app.get("/me")
def get_me(current_user: Usuario = Depends(auth.get_current_user)):
    from limits import get_plan
    return {
        "email": current_user.email,
        "plan": get_plan(current_user),
        "suscripcion_activa": current_user.suscripcion_activa,
        "fecha_vencimiento": current_user.fecha_vencimiento
    }

@app.delete("/historial")
def borrar_historial(current_user: Usuario = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    db.query(Historial).filter(Historial.usuario_id == current_user.id).delete()
    db.commit()
    return {"message": "Historial borrado"}

def verificar_admin(current_user: Usuario = Depends(auth.get_current_user)):
    if not current_user.es_admin:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return current_user

@app.get("/admin/usuarios")
def admin_usuarios(db: Session = Depends(get_db), admin: Usuario = Depends(verificar_admin)):
    from limits import get_plan, PLANES
    from sqlalchemy import func
    usuarios = db.query(Usuario).all()
    resultado = []
    for u in usuarios:
        plan = get_plan(u)
        consultas_hoy = db.query(Historial).filter(
            Historial.usuario_id == u.id,
            Historial.fecha >= datetime(datetime.utcnow().date().year, datetime.utcnow().date().month, datetime.utcnow().date().day)
        ).count()
        consultas_total = db.query(Historial).filter(Historial.usuario_id == u.id).count()
        conexiones = db.query(Conexion).filter(Conexion.usuario_id == u.id).count()
        resultado.append({
            "id": u.id,
            "email": u.email,
            "plan": plan,
            "suscripcion_activa": u.suscripcion_activa,
            "es_admin": u.es_admin,
            "fecha_registro": u.fecha_registro,
            "fecha_vencimiento": u.fecha_vencimiento,
            "consultas_hoy": consultas_hoy,
            "consultas_total": consultas_total,
            "conexiones": conexiones,
            "limite_consultas": PLANES[plan]["consultas_por_dia"],
            "limite_conexiones": PLANES[plan]["conexiones_max"]
        })
    return resultado

@app.patch("/admin/usuarios/{id}/plan")
def admin_cambiar_plan(id: int, data: dict, db: Session = Depends(get_db), admin: Usuario = Depends(verificar_admin)):
    usuario = db.query(Usuario).filter(Usuario.id == id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    usuario.tipo_suscripcion = data.get("plan")
    usuario.suscripcion_activa = data.get("suscripcion_activa", True)
    db.commit()
    return {"message": "Plan actualizado"}

@app.delete("/admin/usuarios/{id}")
def admin_eliminar_usuario(id: int, db: Session = Depends(get_db), admin: Usuario = Depends(verificar_admin)):
    usuario = db.query(Usuario).filter(Usuario.id == id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    db.query(Historial).filter(Historial.usuario_id == id).delete()
    db.query(Conexion).filter(Conexion.usuario_id == id).delete()
    db.delete(usuario)
    db.commit()
    return {"message": "Usuario eliminado"}

@app.get("/admin/metricas")
def admin_metricas(db: Session = Depends(get_db), admin: Usuario = Depends(verificar_admin)):
    from datetime import date
    hoy = date.today()
    total_usuarios = db.query(Usuario).count()
    usuarios_activos = db.query(Usuario).filter(Usuario.suscripcion_activa == True).count()
    consultas_hoy = db.query(Historial).filter(
        Historial.fecha >= datetime(hoy.year, hoy.month, hoy.day)
    ).count()
    consultas_total = db.query(Historial).count()
    por_plan = {}
    for plan in ["gratuito", "basico", "pro", "enterprise"]:
        por_plan[plan] = db.query(Usuario).filter(Usuario.tipo_suscripcion == plan).count()
    return {
        "total_usuarios": total_usuarios,
        "usuarios_activos": usuarios_activos,
        "consultas_hoy": consultas_hoy,
        "consultas_total": consultas_total,
        "por_plan": por_plan
    }