import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()

# URL de la base de datos

user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
host = os.getenv('DB_HOST')
port = os.getenv('DB_PORT')
db_nombre = os.getenv('DB_NAME')

DATABASE_URL = (
    f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db_nombre}?client_encoding=utf8"
)

# Motor de conexión
engine = create_engine(
    DATABASE_URL,
    connect_args={"options": "-c client_encoding=UTF8"}
)
# Fábrica de sesiones
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clase base de todos los modelos
Base = declarative_base()

# Generador FastAPI para cada endpoint
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()