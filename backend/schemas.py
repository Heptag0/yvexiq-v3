from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum

class UsuarioCreate(BaseModel):
    email: str
    password: str

class UsuarioLogin(BaseModel):
    email: str
    password: str

class ModoConsulta(str, Enum):
    rapido = "rapido"
    profundo = "profundo"
    
class Consulta(BaseModel):
    pregunta: str
    conexion_id: int
    modo: ModoConsulta = ModoConsulta.profundo

class ConexionCreate(BaseModel):
    tipo_bd: str
    nombre: str
    ruta_archivo: str

class ConexionResponse(BaseModel):
    id: int
    nombre: str
    tipo_bd: str
    ruta_archivo: str
    usuario_id: int
    fecha_ultima_sincronizacion: Optional[datetime] = None

    class Config:
        from_attributes = True

class HistorialResponse(BaseModel):
    id: int
    pregunta: str
    respuesta: Optional[str] = None
    fecha: datetime
    conexion_id: int

    class Config:
        from_attributes = True

