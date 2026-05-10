import anthropic
from dotenv import load_dotenv
import os

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
model = "claude-haiku-4-5"

def generate_sql(question, schema):
    mensaje =client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user",
                   "content": f"Eres un experto en SQL y estas asistiendo a un negocio por  lo que debes de generar un codigo SQL para la siguiente pregunta: {question} usando el siguiente esquema para responder de forma correcta: {schema} Solo debes de responder con el codigo SQL, sin ninguna explicacion ni informacion extra. Sin bloques de codigo markdown, sin backticks, solo el SQL puro. Usa sintaxis SQLite. En vez de TOP usa LIMIT al final de la query."}
        ]
    )
    return mensaje.content[0].text