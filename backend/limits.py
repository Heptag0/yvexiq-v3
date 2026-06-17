from datetime import datetime, date
from sqlalchemy.orm import Session
from models import Historial, Conexion
from fastapi import HTTPException

PLANES = {
    "gratuito": {
        "consultas_por_dia": 3,
        "conexiones_max": 1,
    },
    "basico": {
        "consultas_por_dia": 30,
        "conexiones_max": 2,
    },
    "pro": {
        "consultas_por_dia": None,
        "conexiones_max": 5,
    },
    "enterprise": {
        "consultas_por_dia": None,  
        "conexiones_max": None,     
    },
}

def get_plan(usuario):
    plan = usuario.tipo_suscripcion

    if not plan or plan not in PLANES:
        return "gratuito"
    if usuario.fecha_vencimiento and usuario.fecha_vencimiento < datetime.utcnow():
        return "gratuito"
    if plan != "gratuito" and not usuario.suscripcion_activa:
        return "gratuito"
        
    return plan

def verificar_limite_consultas(usuario, db: Session):
    plan = get_plan(usuario)
    limite = PLANES[plan]["consultas_por_dia"]

    if limite is None:
        return

    hoy = date.today()
    consultas_hoy = db.query(Historial).filter(
        Historial.usuario_id == usuario.id,
        Historial.fecha >= datetime(hoy.year, hoy.month, hoy.day, 0, 0, 0)
    ).count()

    if consultas_hoy >= limite:
        raise HTTPException(
            status_code=429,
            detail={
                "codigo": "limite_consultas",
                "mensaje": f"Límite diario alcanzado ({limite} consultas/día en plan {plan}). Actualiza tu plan para continuar.",
                "limite": limite,
                "plan": plan
            }
        )

def verificar_limite_conexiones(usuario, db: Session):
    plan = get_plan(usuario)
    limite = PLANES[plan]["conexiones_max"]

    if limite is None:
        return

    conexiones_actuales = db.query(Conexion).filter(
        Conexion.usuario_id == usuario.id
    ).count()

    if conexiones_actuales >= limite:
        raise HTTPException(
            status_code=403,
            detail={
                "codigo": "limite_conexiones",
                "mensaje": f"Límite de conexiones alcanzado ({limite} en plan {plan}). Actualiza tu plan para agregar más.",
                "limite": limite,
                "plan": plan
            }
        )
