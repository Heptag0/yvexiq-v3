import anthropic
from dotenv import load_dotenv
import os

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
model = "claude-haiku-4-5"

def generate_sql(question, schema, tipo_db="csv"):
    if tipo_db == "firebird":
        instruccion_dialecto = "Usa sintaxis Firebird. En vez de LIMIT usa FIRST. Ejemplo: SELECT FIRST 5 * FROM tabla."
    else:
        instruccion_dialecto = "Usa sintaxis SQLite. En vez de TOP usa LIMIT al final."
    mensaje =client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user",
                   "content": f"Eres un experto en SQL y estás asistiendo a un negocio. Genera un código SQL para la siguiente pregunta: {question} usando el siguiente esquema: {schema} Solo responde con el código SQL puro, sin explicaciones, sin markdown, sin backticks. {instruccion_dialecto}. Tambien usa exactamente los nombres de columnas y tablas que aparecen en el schema, sin modificarlos ni abreviarlos."}
        ]
    )
    return mensaje.content[0].text



def generate_explanation(pregunta, sql, resultados):
    mensaje = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user",
               "content": f"Eres un experto analista en negocios, el usuario ha preguntado: {pregunta}, y se ha generado este SQL: {sql}, dando estos resultados: {resultados}. Tu mision como experto es explicar de forma clara, concisa y precisa los datos al dueño del negocio, sin usar lenguaje tecnico."}]
    )
    return mensaje.content[0].text

def generate_chart(pregunta, resultados):
    mensaje = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user",
                   "content": f"A partir de esta pregunta: {pregunta} y estos resultados: {resultados}, genera un grafico profesional y elegante en base a estos datos. SOLO debes de devolver un JSON valido de ECHARTS, sin ninguna explicacion, sin markdown, sin backticks... SOLO el JSON valido. No uses JavaScript dentro del JSON. Solo valores estáticos: strings, números, arrays y objetos."}]
    )
    respuesta = mensaje.content[0].text
    respuesta = respuesta.replace("```json", "").replace("```", "").strip()
    return respuesta
