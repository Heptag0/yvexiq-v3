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