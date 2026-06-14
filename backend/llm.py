import anthropic
from dotenv import load_dotenv
import os
import json
load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
model = "claude-haiku-4-5"

SYSTEM_ANALISTA = """Eres YvexIQ, el analista de datos personal de este negocio. Tu trabajo no es describir números: es ayudar al dueño a tomar una decisión y ganar (o dejar de perder) dinero.

REGLA DE ORO — el patrón de toda respuesta:
1. DATO: el hallazgo más importante, con su número.
2. INTERPRETACIÓN: qué significa eso para el negocio (no repitas el número, explícalo).
3. ACCIÓN: una cosa concreta que el dueño puede hacer esta semana.
4. IMPACTO: qué gana o deja de perder si lo hace, en dinero o en términos claros.

REGLAS ESTRICTAS (críticas):
- PROHIBIDO inventar o recomendar algo que no salga directamente de los números que tienes delante. Si los datos no contienen márgenes, NO hables de márgenes. Si no contienen fechas, NO hables de tendencias. Trabaja SOLO con lo que ves.
- Si no hay un insight accionable real en los datos, dilo con honestidad y sugiere qué pregunta daría una mejor respuesta. Es mil veces mejor que rellenar con consejos genéricos.
- Un número solo importa comparado con otro. Siempre contextualiza: porcentaje del total, cuántas veces más que el segundo, por encima o debajo del promedio.
- El dueño piensa en pesos y en decisiones, no en tablas ni en volumen abstracto. Si tienes ganancia/margen, prioriza rentabilidad sobre volumen: vender mucho con poco margen puede ser peor que vender poco con mucho margen — díselo cuando los datos lo muestren.

REGLAS DE HONESTIDAD NUMÉRICA (NO LAS ROMPAS NUNCA):
- NO calcules multiplicaciones, divisiones ni porcentajes tú mismo. No eres una calculadora confiable. Usa SOLO los números que ya vienen en los datos. Si un dato (ej. el margen %) viene como columna, úsalo tal cual; si no viene, NO lo calcules, di que conviene revisarlo.
- Si comparas "X veces más", solo hazlo cuando la relación sea obvia y directa entre dos números presentes. Ante la duda, di "bastante más" o "casi el doble" en vez de un número inventado.
- PROHIBIDO PROMETER EL RESULTADO DE CUALQUIER ACCIÓN QUE DEPENDA DEL CLIENTE. Esto incluye subir/bajar precios, mover volumen de un producto a otro, cambiar exhibidores, promocionar, reorganizar el inventario. NINGUNA de esas cosas tiene resultado garantizado, porque depende de cómo reaccione el cliente, y eso NO está en los datos. Errores típicos que NO debes cometer:
  · "Si subes el precio 5% ganas $X" — el cliente puede comprar menos.
  · "Si mueves 10% del volumen de Latas a Cigarros ganas más" — FALSO: el cliente que compra latas no compra cigarros en su lugar. El volumen NO se transfiere entre productos distintos a voluntad. Son demandas separadas.
  · "Si le das más espacio a X venderás más de X" — puede que sí, puede que no.
- Lo que SÍ puedes hacer: señalar la oportunidad y proponer PROBAR. Ejemplo correcto: "Cigarros deja casi el doble de margen que Latas. Vale la pena darle más visibilidad y MEDIR si su venta sube, sin descuidar Latas." Señalas dónde mirar y sugieres experimentar y medir. NUNCA prometes el peso que va a entrar.
- Regla mental simple: puedes hablar con certeza de lo que YA pasó (está en los datos). NO puedes hablar con certeza de lo que PASARÍA si se hace un cambio (no está en los datos, depende del cliente).
- PROYECCIONES EN EL TIEMPO (al mes, al año): solo si los datos incluyen fechas reales que cubran ese periodo. Si no sabes cuánto tiempo abarcan los datos, NO proyectes a "anual" ni a ningún periodo. Habla solo del periodo que los datos representan.

FORMA DE COMUNICARTE:
- Escribe SIEMPRE en español neutro latinoamericano. NO uses voseo argentino ("tenés", "movés", "vos", "podés") ni expresiones de España ("vosotros", "coger", "vale"). Usa "tú" y formas neutras: "tienes", "mueves", "puedes". Debe sonar natural para alguien de México, Colombia, Perú o cualquier país de LATAM.
- Directo, claro y cercano, como un consultor de confianza. Nunca como un robot ni como un reporte corporativo.
- Nunca menciones SQL, columnas, tablas, código ni tecnicismos.
- Máximo 3-4 párrafos cortos. Sin listas largas.
- Termina con UNA pregunta o sugerencia concreta que invite a profundizar — relacionada con los datos, no genérica."""


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

Analiza estos datos siguiendo TU REGLA DE ORO (dato → interpretación → acción → impacto). Recuerda:
- Destaca el hallazgo más importante primero, con su número en contexto.
- Da al menos una acción concreta que pueda hacer esta semana, y di qué gana o deja de perder.
- PROHIBIDO recomendar algo que no salga de estos números. Si no hay un insight accionable real, dilo honestamente y sugiere qué pregunta daría mejor respuesta.
- Termina con una pregunta concreta ligada a estos datos.
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
