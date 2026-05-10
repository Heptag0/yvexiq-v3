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

class Conexion(Base):
    __tablename__ = "conexiones"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    nombre = Column(String)
    tipo_bd = Column(String)
    ruta_archivo = Column(String)
    fecha_creacion = Column(DateTime)
    fecha_ultima_sincronizacion = Column(DateTime)


