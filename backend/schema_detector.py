import pandas as pd
import fdb
import os

# Tablas que NO aportan al análisis (redundantes con otras) — se omiten del esquema
# para ahorrar tokens sin perder capacidad analítica.
# Las CORTE_ son resúmenes precalculados de Eleventa que duplican lo que está en
# VENTATICKETS (la fuente real y completa). Además confunden al modelo, que a veces
# las elige para análisis temporales y se equivoca. VENTATICKETS hace ese trabajo mejor.
TABLAS_OMITIR = {
    "PRODUCTOS_BASE",                  # redundante con PRODUCTOS (solo codigo+descripcion)
    "CORTE_VENTAS_POR_DEPTO",          # se puede calcular de VENTATICKETS_ARTICULOS + DEPARTAMENTOS
    "CORTE_VENTAS_DEPTO_OPERACIONES",  # idem, redundante
    "CORTE_OPERACIONES",               # resumen diario; VENTATICKETS tiene el dato real y completo
    "CORTE_MOVIMIENTOS",               # entradas/salidas de caja; uso marginal, confunde al modelo
}

# Columnas sensibles que NUNCA deben enviarse a la IA ni figurar en el esquema,
# en CUALQUIER tabla. Red de seguridad de privacidad (contraseñas, datos personales).
COLUMNAS_SENSIBLES = {
    "CLAVE", "PASSWORD", "CONTRASENA", "CONTRASEÑA",
    "DIRECCION", "TELEFONO", "CORREO", "EMAIL", "USUARIO", "PERMISOS",
}


def _columna_es_sensible(nombre_columna):
    return nombre_columna.strip().upper() in COLUMNAS_SENSIBLES


def _tabla_se_omite(nombre_tabla):
    return nombre_tabla.strip().upper() in TABLAS_OMITIR


def detectar_schema(ruta_archivo):
    if ruta_archivo.lower().endswith(".csv"):
        df = pd.read_csv(ruta_archivo)
    elif ruta_archivo.lower().endswith(".fdb"):
        conn = fdb.connect(
            host=os.getenv('FIREBIRD_HOST'),
            database=ruta_archivo,
            user=os.getenv('FIREBIRD_USER'),
            password=os.getenv('FIREBIRD_PASSWORD')
        )
        tablas = pd.read_sql("SELECT RDB$RELATION_NAME FROM RDB$RELATIONS WHERE RDB$SYSTEM_FLAG = 0 AND RDB$VIEW_BLR IS NULL", conn)
        schema = "Tablas disponibles:\n"
        for tabla in tablas["RDB$RELATION_NAME"]:
            tabla = tabla.strip()
            columnas = pd.read_sql(f"SELECT RDB$FIELD_NAME FROM RDB$RELATION_FIELDS WHERE RDB$RELATION_NAME = '{tabla}'", conn)
            schema += f"\nTabla: {tabla}\nColumnas:\n"
            for columna in columnas["RDB$FIELD_NAME"]:
                columna = columna.strip()
                try:
                    ejemplos_df = pd.read_sql(f"SELECT FIRST 1 {columna} FROM {tabla}", conn)
                    ejemplos = ejemplos_df[columna].dropna().unique().tolist()
                except:
                    ejemplos = []
                schema += f"- {columna} (ejemplo: {ejemplos})\n"  # <-- dentro del loop
        return schema
    else:
        df = pd.read_excel(ruta_archivo)
    schema = "Tabla: nombre_tabla\nColumnas:\n"
    for columna, tipo in df.dtypes.items():
        ejemplos = df[columna].dropna().unique()[:1].tolist()
        schema += f"- {columna} ({tipo}, ejemplo: {ejemplos})\n"
    return schema


def detectar_schema_sync(carpeta):
    schema = ""
    for archivo in os.listdir(carpeta):
        if archivo.lower().endswith(".csv"):
            nombre_tabla = archivo.replace(".csv", "")
            # Omitir tablas redundantes o no analíticas
            if _tabla_se_omite(nombre_tabla):
                continue
            df = pd.read_csv(os.path.join(carpeta, archivo))
            schema += f"Tabla: {nombre_tabla}\nColumnas:\n"
            for columna in df.columns:
                # Nunca incluir columnas sensibles (contraseñas, datos personales)
                if _columna_es_sensible(columna):
                    continue
                ejemplos = df[columna].dropna().unique()[:1].tolist()
                schema += f"- {columna} (ejemplo: {ejemplos})\n"
    return schema
