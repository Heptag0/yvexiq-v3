from pydantic import BaseModel

class UsuarioCreate(BaseModel):
    email: str
    password: str

class UsuarioLogin(BaseModel):
    email: str
    password: str

class Consulta(BaseModel):
    pregunta: str
    conexion_id: int
