import anthropic
from dotenv import load_dotenv
import os
import json

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
model = "claude-haiku-4-5"

def generate_sql(question, schema, tipo_db="csv"):
    if tipo_db == "firebird":
        instruccion_dialecto = "Usa sintaxis Firebird. En vez de LIMIT usa FIRST. Ejemplo: SELECT FIRST 5 * FROM tabla."
    else:
        instruccion_dialecto = "Usa sintaxis SQLite. En vez de TOP usa LIMIT al final."

    mensaje = client.messages.create(
        model=model,
        max_tokens=1024,
        timeout=30,
        messages=[{"role": "user",
                   "content": f"""Eres un experto en SQL para negocios hispanohablantes.
Schema disponible: {schema}
Pregunta del usuario: {question}
Dialecto: {instruccion_dialecto}

Reglas estrictas:
- Responde SOLO con SQL puro, sin explicaciones, sin markdown, sin backticks
- Usa exactamente los nombres de columnas y tablas del schema, sin modificarlos
- Si la pregunta no está relacionada con los datos (saludos, preguntas informales, etc), responde ÚNICAMENTE con: NO_DATA
"""}]
    )
    respuesta = mensaje.content[0].text.strip()
    if "NO_DATA" in respuesta:
        return "NO_DATA"
    return respuesta


def generate_explanation(pregunta, sql, resultados):
    resultados_limitados = resultados[:50] if len(resultados) > 50 else resultados

    mensaje = client.messages.create(
        model=model,
        max_tokens=1024,
        timeout=30,
        messages=[{"role": "user",
                   "content": f"""Eres un analista de negocios que explica datos a dueños de negocio sin conocimientos técnicos.
Pregunta del usuario: {pregunta}
SQL ejecutado: {sql}
Resultados obtenidos: {resultados_limitados}

Explica los resultados de forma clara, directa y conversacional. Sin lenguaje técnico, sin mencionar SQL. Máximo 3-4 párrafos cortos. Destaca el dato más importante primero.
"""}]
    )
    return mensaje.content[0].text


def generate_chart(pregunta, resultados):
    resultados_limitados = resultados[:50] if len(resultados) > 50 else resultados

    mensaje = client.messages.create(
        model=model,
        max_tokens=1024,
        timeout=30,
        messages=[{"role": "user",
                   "content": f"""Genera una configuración de gráfico ECharts profesional para estos datos.
Pregunta: {pregunta}
Datos: {resultados_limitados}

Reglas estrictas:
- Devuelve SOLO un JSON válido de ECharts
- Sin explicaciones, sin markdown, sin backticks
- Sin JavaScript, solo valores estáticos (strings, números, arrays, objetos)
- Elige el tipo de gráfico más apropiado para los datos (bar, line, pie, etc)
"""}]
    )
    respuesta = mensaje.content[0].text
    respuesta = respuesta.replace("```json", "").replace("```", "").strip()
    try:
        json.loads(respuesta)
        return respuesta
    except:
        return None


def generate_fallback(pregunta, schema, error=""):
    if error == "Pregunta no relacionada con los datos":
        instruccion = f"""El usuario escribió: '{pregunta}'.
Responde como un asistente amigable de análisis de negocio. Si es un saludo, saluda brevemente. Menciona en una línea que puedes ayudarle a consultar los datos de su negocio. Máximo 2-3 líneas, sin formato especial."""
    else:
        instruccion = f"""No pudiste procesar la consulta '{pregunta}' debido a un error.
Explica brevemente en lenguaje simple que no pudiste procesar esa consulta. Sin código SQL ni detalles técnicos. Sugiere 2 preguntas alternativas simples basadas en este schema: {schema}"""

    mensaje = client.messages.create(
        model=model,
        max_tokens=512,
        timeout=30,
        messages=[{"role": "user", "content": instruccion}]
    )
    return mensaje.content[0].text