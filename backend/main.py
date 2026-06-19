from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import engine, Base
from models import Usuario, Conexion, Historial
from schemas import UsuarioCreate, UsuarioLogin, Consulta, ConexionCreate, ConexionResponse, HistorialResponse
from database import get_db
import auth
from llm import generate_sql, generate_explanation, generate_chart, generate_fallback, corregir_sql
from query_executor import ejecutar_query, ejecutar_query_sync
from schema_detector import detectar_schema, detectar_schema_sync
import os
from datetime import datetime, timedelta
from limits import verificar_limite_consultas, verificar_limite_conexiones
import analisis
import secrets
import seguridad
import pagos

from apscheduler.schedulers.background import BackgroundScheduler

def limpiar_cuentas_no_verificadas():
    from database import SessionLocal
    db = SessionLocal()
    try:
        hace_7_dias = datetime.now() - timedelta(days=7)
        db.query(Usuario).filter(
            Usuario.email_verificado == False,
            Usuario.fecha_registro < hace_7_dias
        ).delete()
        db.commit()
    finally:
        db.close()

scheduler = BackgroundScheduler()
scheduler.add_job(limpiar_cuentas_no_verificadas, 'interval', hours=24)
scheduler.start()


# Crear tabla en la base de datos
Base.metadata.create_all(bind=engine)

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yvexiq.com", "https://www.yvexiq.com"],
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
def register_user(user: UsuarioCreate, request: Request, db: Session = Depends(get_db)):
    ip = seguridad.obtener_ip(request)
    # Anti-registro masivo: máx 5 registros por IP en 1 hora
    seguridad.verificar_rate_limit(f"register_ip:{ip}", 5, 3600, "Se han creado demasiadas cuentas desde esta red. Inténtalo más tarde.")
    # Validar formato de email y fuerza de contraseña
    email_limpio = seguridad.validar_email(user.email)
    seguridad.validar_password(user.password)

    existing_user = db.query(Usuario).filter(Usuario.email == email_limpio).first()
    if existing_user is not None:
        raise HTTPException(status_code=400, detail="El correo ya esta registrado")
    password_hash = auth.hash_password(user.password)
    token = secrets.token_hex(32)
    db_user = Usuario(
        email=email_limpio,
        password=password_hash,
        tipo_suscripcion="gratuito",
        suscripcion_activa=True,
        fecha_registro=datetime.now(),
        email_verificado=False,
        token_verificacion=token,
        fecha_token_verificacion=datetime.now()
    )
    db.add(db_user)
    db.commit()
    from email_service import enviar_email_verificacion
    enviar_email_verificacion(email_limpio, token)
    return {"message": "Usuario registrado exitosamente"}

@app.get("/verificar-email")
def verificar_email(token: str, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.token_verificacion == token).first()
    if not usuario:
        raise HTTPException(status_code=400, detail="Token inválido")
    if (datetime.now() - usuario.fecha_token_verificacion).days > 7:
        raise HTTPException(status_code=400, detail="Token expirado")
    usuario.email_verificado = True
    usuario.token_verificacion = None
    db.commit()
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="https://yvexiq.com/login?verificado=1")

@app.post("/reenviar-verificacion")
def reenviar_verificacion(current_user: Usuario = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    if current_user.email_verificado:
        raise HTTPException(status_code=400, detail="Email ya verificado")
    # Máx 3 reenvíos por cuenta cada 15 min, para no quemar la cuota de email
    seguridad.verificar_rate_limit(f"reenvio:{current_user.email}", 3, 900, "Has pedido el correo de verificación varias veces. Espera unos minutos y revisa tu bandeja (y spam).")
    token = secrets.token_hex(32)
    current_user.token_verificacion = token
    current_user.fecha_token_verificacion = datetime.now()
    db.commit()
    from email_service import enviar_email_verificacion
    enviar_email_verificacion(current_user.email, token)
    return {"message": "Email de verificacion reenviado"}

@app.post("/login")
def login_user(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    ip = seguridad.obtener_ip(request)
    # Rate limit por IP: máx 10 intentos en 5 min (frena fuerza bruta distribuida por una IP)
    seguridad.verificar_rate_limit(f"login_ip:{ip}", 10, 300, "Demasiados intentos de inicio de sesión. Espera unos minutos e inténtalo de nuevo.")
    # Rate limit por email: máx 5 intentos en 5 min (frena ataque dirigido a una cuenta)
    email_norm = (form_data.username or "").strip().lower()
    seguridad.verificar_rate_limit(f"login_email:{email_norm}", 5, 300, "Demasiados intentos para esta cuenta. Espera unos minutos e inténtalo de nuevo.")

    db_user = db.query(Usuario).filter(Usuario.email == form_data.username).first()
    if db_user is None:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    if not auth.verify_password(form_data.password, db_user.password):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    # Login correcto: limpiar contadores de rate limit de esta cuenta/IP
    seguridad.registrar_exito(f"login_email:{email_norm}")
    seguridad.registrar_exito(f"login_ip:{ip}")

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
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7
    )
    return response
@app.post("/consultar")
def consultar(consulta: Consulta, current_user: Usuario = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    verificar_limite_consultas(current_user, db)
    conexion_id = consulta.conexion_id
    db_conexion = db.query(Conexion).filter(Conexion.id == conexion_id).first()
    if db_conexion is None:
        raise HTTPException(status_code=404, detail={"codigo": "conexion_no_encontrada", "mensaje": "Conexión no encontrada"})
    if db_conexion.usuario_id != current_user.id:
        raise HTTPException(status_code=403, detail={"codigo": "sin_permiso", "mensaje": "No tienes permiso para acceder a esta conexión"})
    carpeta = f"data/{current_user.id}/{conexion_id}"
    if not os.path.exists(carpeta):
        return {"error": "Esta conexión no tiene datos sincronizados. Ejecuta el agente para sincronizar.", "codigo": "sin_datos"}
    schema = detectar_schema_sync(carpeta)
    sql = generate_sql(consulta.pregunta, schema, "csv", consulta.modo)
    if sql.strip() == "NO_DATA":
        respuesta = generate_fallback(consulta.pregunta, schema, "Pregunta no relacionada con los datos")
        return {"explicacion": respuesta, "resultados": [], "graficos": None}
    try:
        try:
            resultados = ejecutar_query_sync(sql, carpeta)
        except Exception as e_sql:
            # El SQL fallo (nombre de tabla/columna, sintaxis): un reintento corrigiendolo
            sql_corregido = corregir_sql(consulta.pregunta, schema, sql, str(e_sql), "csv")
            if sql_corregido.strip() == "NO_DATA":
                respuesta = generate_fallback(consulta.pregunta, schema, "Pregunta no relacionada con los datos")
                return {"explicacion": respuesta, "resultados": [], "graficos": None}
            sql = sql_corregido
            resultados = ejecutar_query_sync(sql, carpeta)

        if consulta.modo == "rapido":
            db_historial = Historial(
                usuario_id=current_user.id,
                conexion_id=conexion_id,
                pregunta=consulta.pregunta,
                respuesta=str(resultados[:30]),
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

def _validar_conexion(conexion_id, current_user, db):
    """Valida que la conexion exista, pertenezca al usuario y tenga datos. Devuelve la carpeta."""
    db_conexion = db.query(Conexion).filter(Conexion.id == conexion_id).first()
    if db_conexion is None:
        raise HTTPException(status_code=404, detail={"codigo": "conexion_no_encontrada", "mensaje": "Conexión no encontrada"})
    if db_conexion.usuario_id != current_user.id:
        raise HTTPException(status_code=403, detail={"codigo": "sin_permiso", "mensaje": "No tienes permiso para acceder a esta conexión"})
    carpeta = f"data/{current_user.id}/{conexion_id}"
    if not os.path.exists(carpeta):
        raise HTTPException(status_code=400, detail={"codigo": "sin_datos", "mensaje": "Esta conexión no tiene datos sincronizados."})
    return carpeta


@app.get("/agenda/fechas")
def agenda_fechas(conexion_id: int, current_user: Usuario = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Rango de fechas con datos, para poblar el selector de la agenda."""
    carpeta = _validar_conexion(conexion_id, current_user, db)
    return analisis.fechas_disponibles(carpeta)


@app.get("/agenda/dia")
def agenda_dia(conexion_id: int, fecha: str, current_user: Usuario = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Corte determinista de un día (fecha = 'YYYY-MM-DD'). Números exactos por SQL/pandas, no por el modelo."""
    carpeta = _validar_conexion(conexion_id, current_user, db)
    resumen = analisis.resumen_dia(carpeta, fecha)
    return resumen


@app.get("/alertas")
def alertas(conexion_id: int, current_user: Usuario = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Alertas proactivas deterministas: detecta anomalías reales en los últimos 30 días."""
    carpeta = _validar_conexion(conexion_id, current_user, db)
    return analisis.generar_alertas(carpeta, dias_ventana=30)


@app.post("/sync")
def sincronizar(conexion_id: int, current_user: Usuario = Depends(auth.get_current_user), db: Session = Depends(get_db), archivo: UploadFile = File(...)):
    EXTENSIONES_PERMITIDAS = {".csv", ".xlsx", ".xls", ".fdb"}
    # Sanear el nombre: usar SOLO el nombre base, sin rutas, para evitar path traversal (../../)
    nombre_seguro = os.path.basename(archivo.filename or "")
    nombre_seguro = nombre_seguro.replace("\\", "").replace("/", "").strip()
    if not nombre_seguro:
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido.")
    extension = os.path.splitext(nombre_seguro)[1].lower()
    if extension not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(status_code=400, detail="Tipo de archivo no permitido. Solo CSV, Excel y Firebird.")

    db_conexion = db.query(Conexion).filter(Conexion.id == conexion_id).first()
    if db_conexion is None:
        raise HTTPException(status_code=404, detail="Conexion no encontrada")
    if db_conexion.usuario_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para acceder a esta conexion")

    contenido = archivo.file.read()
    carpeta = f"data/{current_user.id}/{conexion_id}"
    os.makedirs(carpeta, exist_ok=True)
    ruta_destino = os.path.join(carpeta, nombre_seguro)
    # Verificación extra: la ruta final debe quedar DENTRO de la carpeta del usuario
    if not os.path.abspath(ruta_destino).startswith(os.path.abspath(carpeta) + os.sep):
        raise HTTPException(status_code=400, detail="Ruta de archivo inválida.")
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
    db.query(Historial).filter(Historial.conexion_id == id).delete()
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
        "fecha_inicio_suscripcion": current_user.fecha_inicio_suscripcion,
        "fecha_vencimiento": current_user.fecha_vencimiento,
        "email_verificado": current_user.email_verificado,
        "tiene_suscripcion_mp": bool(current_user.preapproval_id),
    }


@app.post("/cuenta/cambiar-password")
def cambiar_password(data: dict, current_user: Usuario = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Cambia la contraseña del usuario. Requiere la contraseña actual."""
    actual = data.get("password_actual", "")
    nueva = data.get("password_nueva", "")

    # Verificar la contraseña actual
    if not auth.verify_password(actual, current_user.password):
        raise HTTPException(status_code=400, detail={"codigo": "password_incorrecta", "mensaje": "La contraseña actual no es correcta."})

    # Validar la nueva contraseña (mismas reglas que el registro)
    try:
        seguridad.validar_password(nueva)
    except Exception:
        raise HTTPException(status_code=400, detail={"codigo": "password_invalida", "mensaje": "La nueva contraseña no cumple los requisitos mínimos."})

    current_user.password = auth.hash_password(nueva)
    db.commit()
    return {"mensaje": "Contraseña actualizada correctamente."}


@app.post("/suscripcion/cancelar")
def cancelar_mi_suscripcion(current_user: Usuario = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Cancela la suscripción activa del usuario en Mercado Pago y la pasa a gratuito."""
    if not current_user.preapproval_id:
        raise HTTPException(status_code=400, detail={"codigo": "sin_suscripcion", "mensaje": "No tienes una suscripción activa que cancelar."})

    try:
        pagos.cancelar_suscripcion(current_user.preapproval_id)
    except ValueError:
        raise HTTPException(status_code=502, detail={"codigo": "error_cancelar", "mensaje": "No se pudo cancelar la suscripción en este momento. Intenta más tarde o contáctanos."})

    # Actualizar la cuenta a gratuito
    current_user.suscripcion_activa = False
    current_user.tipo_suscripcion = "gratuito"
    current_user.preapproval_id = None
    db.commit()
    return {"mensaje": "Tu suscripción fue cancelada. Seguirás teniendo acceso hasta el final del periodo ya pagado."}


@app.delete("/cuenta/eliminar")
def eliminar_mi_cuenta(data: dict, current_user: Usuario = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Elimina la cuenta del usuario. Requiere confirmación con contraseña."""
    password = data.get("password", "")
    if not auth.verify_password(password, current_user.password):
        raise HTTPException(status_code=400, detail={"codigo": "password_incorrecta", "mensaje": "Contraseña incorrecta. No se eliminó la cuenta."})

    # Si tiene suscripción activa en MP, intentar cancelarla antes de borrar
    if current_user.preapproval_id:
        try:
            pagos.cancelar_suscripcion(current_user.preapproval_id)
        except Exception:
            pass  # si falla, seguimos con el borrado igualmente

    user_id = current_user.id
    # Borrar datos asociados
    db.query(Historial).filter(Historial.usuario_id == user_id).delete()
    db.query(Conexion).filter(Conexion.usuario_id == user_id).delete()
    db.query(Usuario).filter(Usuario.id == user_id).delete()
    db.commit()
    return {"mensaje": "Tu cuenta y todos tus datos fueron eliminados."}

@app.delete("/historial")
def borrar_historial(current_user: Usuario = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    db.query(Historial).filter(Historial.usuario_id == current_user.id).delete()
    db.commit()
    return {"message": "Historial borrado"}

def verificar_admin(current_user: Usuario = Depends(auth.get_current_user)):
    if not current_user.es_admin:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return current_user


# ════════════════════════════════════════════
#   PAGOS — Mercado Pago (suscripciones)
# ════════════════════════════════════════════

@app.post("/suscripcion/crear")
def crear_suscripcion(data: dict, current_user: Usuario = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """
    Devuelve el link de checkout de Mercado Pago para el plan elegido.
    data: {"plan": "basico"|"pro", "periodo": "mensual"|"anual"}
    """
    if not pagos.esta_configurado():
        raise HTTPException(status_code=503, detail={"codigo": "pagos_no_disponibles", "mensaje": "Los pagos no están disponibles en este momento."})

    plan = data.get("plan")
    periodo = data.get("periodo")
    if plan not in ("basico", "pro") or periodo not in ("mensual", "anual"):
        raise HTTPException(status_code=400, detail={"codigo": "plan_invalido", "mensaje": "Plan o periodo no válido."})

    try:
        resultado = pagos.crear_suscripcion(
            plan=plan,
            periodo=periodo,
            email_usuario=current_user.email,
            referencia=current_user.id,
        )
    except ValueError:
        raise HTTPException(status_code=502, detail={"codigo": "error_pago", "mensaje": "No se pudo iniciar el pago. Intenta de nuevo más tarde."})

    return {"init_point": resultado["init_point"], "preapproval_id": resultado["preapproval_id"]}


@app.post("/webhook/mercadopago")
async def webhook_mercadopago(request: Request, db: Session = Depends(get_db)):
    """
    Recibe notificaciones de Mercado Pago sobre cambios en las suscripciones.
    Verifica el estado REAL consultando a MP (no confía en el cuerpo del webhook)
    y activa o desactiva el plan del usuario según corresponda.
    """
    # MP envía el id del recurso por query o por body, según el tipo de notificación
    try:
        body = await request.json()
    except Exception:
        body = {}

    # Identificar la suscripción afectada
    tipo = body.get("type") or request.query_params.get("type")
    preapproval_id = None
    if body.get("data") and isinstance(body["data"], dict):
        preapproval_id = body["data"].get("id")
    if not preapproval_id:
        preapproval_id = request.query_params.get("id") or request.query_params.get("data.id")

    # Solo nos interesan notificaciones de suscripciones
    if not preapproval_id:
        return {"status": "ignored"}

    # Consultar el estado REAL en Mercado Pago (no confiar en el webhook a ciegas)
    try:
        sub = pagos.consultar_suscripcion(preapproval_id)
    except Exception:
        # Si no se pudo consultar, devolvemos 200 para que MP no reintente en bucle,
        # pero no cambiamos nada.
        return {"status": "no_verificado"}

    status_mp = sub.get("status")

    # Identificar al usuario: primero por external_reference (si viene), luego por email.
    # Con el enfoque de links de plan, MP comparte el email del pagador (payer_email).
    usuario = None
    referencia = sub.get("external_reference")
    if referencia:
        try:
            usuario = db.query(Usuario).filter(Usuario.id == int(referencia)).first()
        except (ValueError, TypeError):
            usuario = None
    if not usuario:
        email_pagador = sub.get("payer_email")
        if email_pagador:
            usuario = db.query(Usuario).filter(Usuario.email == email_pagador).first()

    if not usuario:
        return {"status": "usuario_no_encontrado"}

    # Aplicar el cambio de plan según el estado real de la suscripción
    if pagos.estado_implica_activo(status_mp):
        # La suscripción está activa y al día. Derivar el plan del nombre (reason).
        plan_detectado, _ = pagos.plan_desde_reason(sub.get("reason"))
        if plan_detectado:
            usuario.tipo_suscripcion = plan_detectado
        usuario.suscripcion_activa = True
        usuario.fecha_inicio_suscripcion = datetime.utcnow()
        usuario.preapproval_id = preapproval_id  # guardamos el id para poder cancelar después
        db.commit()
    else:
        # paused / cancelled / etc. -> el usuario deja de tener plan de pago
        usuario.suscripcion_activa = False
        usuario.tipo_suscripcion = "gratuito"
        usuario.preapproval_id = None
        db.commit()

    return {"status": "ok"}


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
            "limite_conexiones": PLANES[plan]["conexiones_max"],
	    "email_verificado": u.email_verificado,
	    "dias_para_verificar": max(0, 7 - (datetime.now() - u.fecha_registro).days) if not u.email_verificado else None

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

@app.post("/admin/usuarios/{id}/reenviar-verificacion")
def admin_reenviar_verificacion(id: int, db: Session = Depends(get_db), admin: Usuario = Depends(verificar_admin)):
    usuario = db.query(Usuario).filter(Usuario.id == id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if usuario.email_verificado:
        raise HTTPException(status_code=400, detail="Email ya verificado")
    token = secrets.token_hex(32)
    usuario.token_verificacion = token
    usuario.fecha_token_verificacion = datetime.now()
    db.commit()
    from email_service import enviar_email_verificacion
    enviar_email_verificacion(usuario.email, token)
    return {"message": "Email reenviado"}

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

@app.post("/contacto")
def formulario_contacto(data: dict, request: Request):
    ip = seguridad.obtener_ip(request)
    # Máx 5 mensajes de contacto por IP cada 30 min, anti-spam
    seguridad.verificar_rate_limit(f"contacto:{ip}", 5, 1800, "Has enviado varios mensajes. Espera unos minutos antes de enviar otro.")
    nombre = data.get("nombre", "").strip()
    email = data.get("email", "").strip()
    asunto = data.get("asunto", "").strip()
    plan = data.get("plan", "")
    mensaje = data.get("mensaje", "").strip()
    
    if not nombre or not email or not asunto or not mensaje:
        raise HTTPException(status_code=400, detail="Faltan campos obligatorios")
    
    from email_service import enviar_email_contacto
    enviado = enviar_email_contacto(nombre, email, asunto, plan, mensaje)
    
    if not enviado:
        raise HTTPException(status_code=500, detail="Error al enviar el mensaje")
    
    return {"message": "Mensaje enviado correctamente"}


@app.post("/analizar-schema")
def analizar_schema(
    payload: dict,
    current_user: Usuario = Depends(auth.get_current_user)
):
    schema = payload.get("schema", "")
    if not schema:
        raise HTTPException(status_code=400, detail="Schema vacío")
    
    import anthropic as ant
    client = ant.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    mensaje = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=256,
        messages=[{"role": "user", "content": f"Eres un experto en bases de datos de negocios. Aquí está un listado de tablas con su número de filas:\n{schema}\nDevuelve ÚNICAMENTE los nombres de las tablas relevantes para analizar ventas y operaciones del negocio, separados por coma. Solo los nombres, sin explicaciones."}]
    )
    return {"tablas": mensaje.content[0].text}
