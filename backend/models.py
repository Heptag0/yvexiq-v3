from database import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime

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

