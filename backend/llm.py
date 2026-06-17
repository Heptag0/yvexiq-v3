import anthropic
from dotenv import load_dotenv
import os
import json
load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
model = "claude-haiku-4-5"

SYSTEM_ANALISTA = """Eres YvexIQ, el analista de datos personal de este negocio. Hablas con el dueño como lo haría una persona de confianza que entiende de números y de su negocio: cercano, claro y profesional, sin pose corporativa ni frialdad de robot. Tu trabajo no es describir números, es ayudarle a tomar una buena decisión y a ganar (o dejar de perder) dinero.

CÓMO PIENSAS (pero sin decirlo en voz alta):
Internamente sigues un hilo: cuál es el hallazgo importante, qué significa para el negocio, qué podría hacer al respecto, y qué hay en juego. PERO NUNCA escribas ese esquema con etiquetas. PROHIBIDO escribir "DATO:", "INTERPRETACIÓN:", "ACCIÓN:", "IMPACTO:" o cualquier encabezado parecido. Eso suena a formulario llenado por una máquina. En vez de eso, hilvanas todo en una conversación natural, como cuando un amigo que sabe de números te explica algo tomando un café: te dice lo importante, le da sentido, y te sugiere por dónde mirar, todo seguido y fluido.

TONO Y FORMA:
- Suena a persona real, cálida y profesional. Alguien en quien confiar. Ni acartonado ni excesivamente coloquial.
- Sé BREVE. La mayoría de las respuestas caben en 2-3 párrafos cortos. Una pregunta simple merece una respuesta simple y directa, no un ensayo. Solo extiéndete si la pregunta de verdad lo amerita.
- Evita la jerga de consultor ("rebalancear", "eficiencia operativa", "optimizar el mix"). Habla como le hablarías a un tendero inteligente: con palabras normales.
- Empieza por lo que importa, sin rodeos ni preámbulos tipo "He analizado tus datos y...". Ve directo al hallazgo.
- Escribe SIEMPRE en español neutro latinoamericano. NO uses voseo ("tenés", "vos", "podés") ni expresiones de España ("vosotros", "vale", "coger"). Usa "tú": "tienes", "puedes", "mira".
- Nunca menciones SQL, columnas, tablas, código ni tecnicismos.
- No siempre tienes que terminar con una pregunta. Si una pregunta o sugerencia concreta surge natural y aporta, hazla; si no, cierra de forma natural. Que no se sienta como una fórmula obligada al final de cada respuesta.

QUÉ HACE ÚTIL TU RESPUESTA:
- Un número solo importa comparado con otro. Da contexto: porcentaje del total, cuántas veces más que otro, por encima o por debajo del promedio. Pero hazlo de forma conversacional, no como una ficha técnica.
- El dueño piensa en pesos y en decisiones, no en tablas. Si tienes ganancia o margen, prioriza la rentabilidad sobre el volumen cuando los datos lo muestren: a veces vender mucho con poco margen es peor que vender poco con buen margen, y eso vale la pena decírselo claro.
- Si hay algo accionable real, sugiérelo con naturalidad. Si no lo hay, dilo con honestidad en vez de rellenar con consejos genéricos.

REGLAS DE HONESTIDAD (NO LAS ROMPAS NUNCA, por más natural que suenes):
- Trabaja SOLO con los números que tienes delante. Si los datos no traen márgenes, no hables de márgenes. Si no traen fechas, no hables de tendencias. Nunca inventes un dato para rellenar.
- NO calcules multiplicaciones, divisiones ni porcentajes tú mismo: no eres una calculadora confiable. Usa los números tal como vienen. Si el margen ya viene calculado, úsalo; si no viene, no lo inventes, di que conviene revisarlo.
- Al comparar "X veces más", solo si la relación es obvia entre dos números presentes. Ante la duda, di "bastante más" o "casi el doble" en vez de un número inventado.
- NUNCA prometas el resultado de una acción que depende del cliente (subir/bajar precios, mover un producto, cambiar exhibidores, promociones). No sabes cómo reaccionará el cliente, no está en los datos. Error típico: "si subes el precio 5% ganas $X" — falso, el cliente puede comprar menos. Otro: "si mueves volumen de Latas a Cigarros ganas más" — falso, quien compra latas no compra cigarros en su lugar; son demandas distintas.
- Lo que SÍ puedes hacer: señalar la oportunidad e invitar a PROBAR y MEDIR. Ejemplo de cómo decirlo bien y natural: "Los cigarros te dejan casi el doble de margen que las latas. Podrías darles un poco más de visibilidad y ver si su venta sube, sin descuidar lo demás." Señalas dónde mirar y propones experimentar, nunca prometes el dinero que entrará.
- Puedes hablar con certeza de lo que YA pasó (está en los datos). No de lo que PASARÍA si se hace un cambio.
- No proyectes a futuro (al mes, al año) salvo que los datos incluyan fechas reales que cubran ese periodo. Si no sabes cuánto tiempo abarcan los datos, habla solo del periodo que representan."""


def generate_sql(question, schema, tipo_db="csv", modo="profundo"):
    if tipo_db == "firebird":
        instruccion_dialecto = "Usa sintaxis Firebird. En vez de LIMIT usa FIRST. Ejemplo: SELECT FIRST 10 * FROM tabla."
    else:
        instruccion_dialecto = "Usa sintaxis SQLite. Usa LIMIT al final para limitar resultados."

    # En modo profundo, el SQL piensa como analista: enriquece con metricas de apoyo
    # que EXISTAN en el schema. En modo rapido, trae solo lo que se pidio.
    if modo == "profundo":
        instruccion_analitica = """ENRIQUECIMIENTO ANALÍTICO (importante):
Esta consulta alimenta un análisis profundo. No traigas solo lo que se pide literalmente: enriquece la consulta con métricas de apoyo que SÍ existan en el schema, para que el análisis sea útil. Por ejemplo:
- Si preguntan por ventas o productos más vendidos, y el schema tiene columnas de ganancia, costo, margen o utilidad, INCLÚYELAS además del total de ventas.
- IMPORTANTE: si puedes calcular el margen porcentual (ganancia / ventas * 100), AÑÁDELO como columna calculada en el SQL, por ejemplo: ROUND(SUM(ganancia) * 100.0 / SUM(ventas), 1) AS MARGEN_PCT. Así el análisis tiene el porcentaje ya calculado y no hay que estimarlo.
- Si el schema tiene una columna de conteo (número de tickets, turnos, transacciones), incluye un promedio por unidad (ej. venta promedio por ticket) cuando aporte.
- Si hay fechas, considera agrupar o comparar por periodo cuando la pregunta lo permita.
REGLA CLAVE: solo añade columnas que EXISTAN en el schema (las calculadas como MARGEN_PCT sí están permitidas siempre que sus columnas base existan). Nunca inventes columnas base. Si una métrica no existe, no la incluyas — adapta la consulta a lo que realmente hay.
Para preguntas analíticas (más vendido, ranking, totales, comparaciones) SIEMPRE agrega con GROUP BY / SUM / COUNT en vez de traer filas crudas, para que los totales sean correctos."""
    else:
        instruccion_analitica = """Esta consulta es modo rápido: el usuario solo verá la tabla. Trae exactamente lo que pide, sin columnas extra. Para preguntas de ranking o totales, igualmente agrega con GROUP BY / SUM / COUNT para que los números sean correctos."""

    mensaje = client.messages.create(
        model=model,
        max_tokens=1024,
        timeout=30,
        system="Eres un experto en SQL para bases de datos de negocios hispanohablantes. Generas SQL preciso y, cuando se te pide, analíticamente rico, basándote ESTRICTAMENTE en el schema proporcionado.",
        messages=[{"role": "user",
                   "content": f"""Schema disponible:
{schema}

Pregunta del usuario: {question}

Dialecto SQL: {instruccion_dialecto}

{instruccion_analitica}

Reglas estrictas:
- Responde SOLO con SQL puro, sin explicaciones, sin markdown, sin backticks
- Usa exactamente los nombres de columnas y tablas del schema, sin modificarlos ni inventarlos
- Para análisis por periodo (por mes, por año), agrupa SIEMPRE incluyendo el año, no solo el mes. Si comparas meses de un mismo año o entre años, extrae año y mes de la columna de fecha y agrupa por ambos, para no mezclar el mismo mes de años distintos.
- MUY IMPORTANTE para preguntas de "el mejor", "el peor", "el que más/menos", "el máximo", "cuál vendió más" por periodo o categoría: NO uses LIMIT 1 ni traigas una sola fila. Trae TODOS los grupos (todos los meses, todos los productos, etc.) agrupados y ordenados de mayor a menor. El análisis posterior identificará cuál es el mejor a partir del conjunto completo. Traer una sola fila da una respuesta incompleta y engañosa. Ejemplo: para "el mejor mes de 2025", agrupa las ventas por mes de todo 2025 y ordénalas, devolviendo los 12 meses, no solo uno.
- Para análisis de ventas, ganancias o tickets, usa la tabla de tickets/ventas como fuente principal (es la más completa y confiable).
- Limita resultados a máximo 500 filas con LIMIT/FIRST
- Si la pregunta no tiene relación con los datos disponibles (saludos, preguntas generales de negocio sin relación con el schema, etc), responde ÚNICAMENTE con: NO_DATA
- Si la pregunta es sobre datos que no existen en el schema, responde ÚNICAMENTE con: NO_DATA
"""}]
    )
    respuesta = mensaje.content[0].text.strip()
    if "NO_DATA" in respuesta:
        return "NO_DATA"
    # Limpieza defensiva por si el modelo envuelve en backticks
    respuesta = respuesta.replace("```sql", "").replace("```", "").strip()
    return respuesta


def corregir_sql(question, schema, sql_fallido, error, tipo_db="csv"):
    """Reintento: le devuelve a Claude el SQL que fallo y el error para que lo corrija una vez."""
    if tipo_db == "firebird":
        instruccion_dialecto = "Usa sintaxis Firebird. En vez de LIMIT usa FIRST."
    else:
        instruccion_dialecto = "Usa sintaxis SQLite. Usa LIMIT al final."

    mensaje = client.messages.create(
        model=model,
        max_tokens=1024,
        timeout=30,
        system="Eres un experto en SQL. Corriges consultas que fallaron, basándote estrictamente en el schema y en el mensaje de error.",
        messages=[{"role": "user",
                   "content": f"""Schema disponible:
{schema}

Pregunta original del usuario: {question}

Este SQL falló al ejecutarse:
{sql_fallido}

Error recibido:
{error}

Dialecto: {instruccion_dialecto}

Corrige el SQL. Causas comunes: nombre de tabla o columna que no existe en el schema, sintaxis incompatible con el dialecto, función no soportada.
Responde SOLO con el SQL corregido, sin explicaciones, sin markdown, sin backticks.
Usa exactamente los nombres de tablas y columnas tal como aparecen en el schema.
Si la pregunta realmente no se puede responder con este schema, responde ÚNICAMENTE con: NO_DATA"""}]
    )
    respuesta = mensaje.content[0].text.strip()
    if "NO_DATA" in respuesta:
        return "NO_DATA"
    respuesta = respuesta.replace("```sql", "").replace("```", "").strip()
    return respuesta


def generate_explanation(pregunta, sql, resultados, schema=""):
    resultados_limitados = resultados[:50] if len(resultados) > 50 else resultados
    n_resultados = len(resultados)

    mensaje = client.messages.create(
        model=model,
        max_tokens=1024,
        timeout=30,
        system=SYSTEM_ANALISTA,
        messages=[{"role": "user",
                   "content": f"""El dueño del negocio preguntó: "{pregunta}"

Datos obtenidos ({n_resultados} registros en total, mostrando los primeros 50):
{resultados_limitados}

Schema del negocio (para contexto):
{schema}

Responde como YvexIQ: natural, cálido y profesional, como una persona de confianza que sabe de números. Recuerda:
- NO uses encabezados ni etiquetas (nada de "DATO:", "INTERPRETACIÓN:", etc.). Hilvana todo en una conversación fluida.
- Sé breve: ve directo al hallazgo importante y dale sentido en pesos y decisiones. 2-3 párrafos cortos suelen bastar.
- Solo trabaja con estos números. No inventes nada que no esté aquí. Si no hay un hallazgo accionable real, dilo con honestidad.
- No prometas resultados de acciones que dependen del cliente; si acaso, invita a probar y medir.
- Cierra de forma natural. Una pregunta o sugerencia solo si surge genuina, no como fórmula obligada.
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
- Elige el tipo de gráfico más apropiado (bar para comparaciones, line para tendencias, pie para distribuciones)
- Usa colores profesionales: #7c22d4, #a855f7, #d946ef, #c026d3
- Incluye título descriptivo en el gráfico
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
        instruccion = f"""El dueño del negocio escribió: '{pregunta}'

El schema de su negocio incluye: {schema}

Responde como YvexIQ, su analista personal. Si es un saludo, responde de forma cálida y breve. 
Luego menciona 2-3 preguntas concretas e interesantes que podrías responder con los datos disponibles de su negocio.
Máximo 3-4 líneas. Sé específico con los nombres de tablas/productos que ves en el schema."""
    else:
        instruccion = f"""No pudiste procesar la consulta '{pregunta}'.

Schema disponible: {schema}

Como YvexIQ, el analista del negocio, explica brevemente en lenguaje simple que no pudiste procesar esa consulta específica.
Sugiere 2 preguntas alternativas concretas que SÍ puedes responder con los datos disponibles.
Sin tecnicismos, máximo 3 líneas."""

    mensaje = client.messages.create(
        model=model,
        max_tokens=512,
        timeout=30,
        system=SYSTEM_ANALISTA,
        messages=[{"role": "user", "content": instruccion}]
    )
    return mensaje.content[0].text
