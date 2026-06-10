from database import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy import ForeignKey

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    suscripcion_activa = Column(Boolean, default=False)
    tipo_suscripcion = Column(String)
    fecha_inicio_suscripcion = Column(DateTime)
    fecha_vencimiento = Column(DateTime)
    fecha_registro = Column(DateTime)
    refresh_token = Column(String, nullable=True)
    es_admin = Column(Boolean, default=False)
    email_verificado = Column(Boolean, default=False)
    token_verificacion = Column(String(64), nullable=True)
    fecha_token_verificacion = Column(DateTime, nullable=True)
class Conexion(Base):
    __tablename__ = "conexiones"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    nombre = Column(String)
    tipo_bd = Column(String)
    ruta_archivo = Column(String)
    fecha_creacion = Column(DateTime)
    fecha_ultima_sincronizacion = Column(DateTime)

class Historial(Base):
    __tablename__ = "historial"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    conexion_id = Column(Integer, ForeignKey("conexiones.id"))
    pregunta = Column(String)
    fecha = Column(DateTime)
    respuesta = Column(String, nullable=True)


