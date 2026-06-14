"""
analisis.py — Análisis determinista para YvexIQ.
Genera cortes de día y alertas con SQL exacto (no depende del modelo para los números).
Diseñado para ser universal: descubre dinámicamente la tabla de ventas y sus columnas,
en vez de asumir nombres concretos de un POS específico.
"""
import pandas as pd
import pandasql as ps
import os
import unicodedata


def _norm(texto):
    """Normaliza un nombre de columna: minúsculas, sin acentos, sin espacios raros."""
    if texto is None:
        return ""
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    return t.lower().strip()


# Sinónimos por concepto. Universal: cubre nombres comunes en español/inglés de distintos POS.
SINONIMOS = {
    "fecha":   ["vendido_en", "fecha_venta", "fecha", "vendido", "sold_at", "date", "sale_date", "created_at", "creado_en", "timestamp"],
    "total":   ["total", "monto", "importe", "venta_total", "amount", "subtotal", "total_venta"],
    "ganancia":["ganancia", "utilidad", "profit", "margen_bruto", "ganancia_neta"],
    "margen":  ["margen_pct", "margen", "margin", "margin_pct"],
    "articulos":["numero_articulos", "articulos", "items", "cantidad", "num_items", "qty"],
    "pago":    ["forma_pago", "metodo_pago", "payment", "tipo_pago", "pago"],
    "cancelado":["esta_cancelado", "cancelado", "is_cancelled", "cancelada", "anulado"],
    "cajero":  ["cajero_id", "cajero", "vendedor", "usuario_id", "cashier", "empleado"],
}


def _detectar_columnas(df):
    """Mapea conceptos → nombre real de columna en este DataFrame. Devuelve dict."""
    cols_norm = { _norm(c): c for c in df.columns }
    encontrado = {}
    for concepto, candidatos in SINONIMOS.items():
        for cand in candidatos:
            if cand in cols_norm:
                encontrado[concepto] = cols_norm[cand]
                break
    return encontrado


def _cargar_tabla_ventas(carpeta):
    """
    Carga los CSV de la carpeta y elige la tabla que parece de ventas:
    la que tenga columna de fecha Y de total. Devuelve (nombre, df, columnas_detectadas).
    """
    mejor = None
    for archivo in os.listdir(carpeta):
        if not archivo.lower().endswith(".csv"):
            continue
        ruta = os.path.join(carpeta, archivo)
        try:
            df = pd.read_csv(ruta)
        except Exception:
            continue
        cols = _detectar_columnas(df)
        # candidata válida: tiene fecha y total
        if "fecha" in cols and "total" in cols:
            nombre = archivo.replace(".csv", "")
            # preferimos la tabla con más filas (la principal de ventas)
            if mejor is None or len(df) > len(mejor[1]):
                mejor = (nombre, df, cols)
    return mejor  # None si no hay ninguna


def resumen_dia(carpeta, fecha):
    """
    Corte determinista de un día. fecha en formato 'YYYY-MM-DD'.
    Devuelve dict con métricas exactas o un dict con 'error'.
    """
    tabla = _cargar_tabla_ventas(carpeta)
    if tabla is None:
        return {"error": "no_ventas", "mensaje": "No encontré una tabla de ventas con fecha y total en tus datos sincronizados."}

    nombre, df, cols = tabla
    col_fecha = cols["fecha"]
    col_total = cols["total"]
    col_gan = cols.get("ganancia")
    col_canc = cols.get("cancelado")

    # Normalizamos la fecha a tipo datetime para poder filtrar por día con seguridad
    df = df.copy()
    df["_fecha_dt"] = pd.to_datetime(df[col_fecha], errors="coerce")
    df_dia = df[df["_fecha_dt"].dt.strftime("%Y-%m-%d") == fecha]

    # Excluir tickets cancelados si existe esa columna
    if col_canc and col_canc in df_dia.columns:
        # cancelado puede venir como 'f'/'t', True/False, 0/1
        canc_norm = df_dia[col_canc].astype(str).str.lower().str.strip()
        df_dia = df_dia[~canc_norm.isin(["t", "true", "1", "si", "sí", "yes"])]

    n_tickets = len(df_dia)
    if n_tickets == 0:
        return {
            "fecha": fecha, "sin_datos": True,
            "total": 0, "tickets": 0, "ticket_promedio": 0,
            "ganancia": 0, "margen_pct": 0,
            "por_hora": [], "por_pago": [], "tabla": nombre
        }

    total = float(pd.to_numeric(df_dia[col_total], errors="coerce").fillna(0).sum())
    ganancia = float(pd.to_numeric(df_dia[col_gan], errors="coerce").fillna(0).sum()) if col_gan else None
    ticket_prom = total / n_tickets if n_tickets else 0
    margen = (ganancia * 100.0 / total) if (ganancia is not None and total > 0) else None

    # Ventas por hora (0-23)
    df_dia = df_dia.copy()
    df_dia["_hora"] = df_dia["_fecha_dt"].dt.hour
    por_hora_series = df_dia.groupby("_hora").apply(
        lambda g: float(pd.to_numeric(g[col_total], errors="coerce").fillna(0).sum())
    )
    por_hora = [{"hora": int(h), "total": round(v, 2)} for h, v in por_hora_series.items()]

    # Desglose por forma de pago (si existe)
    por_pago = []
    col_pago = cols.get("pago")
    if col_pago and col_pago in df_dia.columns:
        pago_series = df_dia.groupby(col_pago).apply(
            lambda g: float(pd.to_numeric(g[col_total], errors="coerce").fillna(0).sum())
        )
        por_pago = [{"forma": str(k), "total": round(v, 2)} for k, v in pago_series.items()]

    return {
        "fecha": fecha,
        "sin_datos": False,
        "total": round(total, 2),
        "tickets": n_tickets,
        "ticket_promedio": round(ticket_prom, 2),
        "ganancia": round(ganancia, 2) if ganancia is not None else None,
        "margen_pct": round(margen, 2) if margen is not None else None,
        "por_hora": por_hora,
        "por_pago": por_pago,
        "tabla": nombre,
    }


def fechas_disponibles(carpeta):
    """Devuelve el rango de fechas con datos (min y max) y lista de días disponibles."""
    tabla = _cargar_tabla_ventas(carpeta)
    if tabla is None:
        return {"error": "no_ventas"}
    nombre, df, cols = tabla
    fechas = pd.to_datetime(df[cols["fecha"]], errors="coerce").dropna()
    if len(fechas) == 0:
        return {"error": "sin_fechas"}
    dias = sorted(fechas.dt.strftime("%Y-%m-%d").unique().tolist())
    return {"min": dias[0], "max": dias[-1], "dias": dias}


# ════════════════════════════════════════════════
#   ALERTAS PROACTIVAS (deterministas y conservadoras)
# ════════════════════════════════════════════════

DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _preparar_ventas(carpeta, dias_ventana=30):
    """Carga la tabla de ventas, normaliza fecha y la limita a la ventana reciente."""
    tabla = _cargar_tabla_ventas(carpeta)
    if tabla is None:
        return None
    nombre, df, cols = tabla
    df = df.copy()
    df["_dt"] = pd.to_datetime(df[cols["fecha"]], errors="coerce")
    df = df.dropna(subset=["_dt"])
    if len(df) == 0:
        return None
    # Excluir cancelados
    col_canc = cols.get("cancelado")
    if col_canc and col_canc in df.columns:
        canc = df[col_canc].astype(str).str.lower().str.strip()
        df = df[~canc.isin(["t", "true", "1", "si", "sí", "yes"])]
    # Ventana reciente: desde el último día con datos hacia atrás
    ultimo = df["_dt"].max().normalize()
    inicio = ultimo - pd.Timedelta(days=dias_ventana - 1)
    df_ventana = df[df["_dt"] >= inicio].copy()
    df_ventana["_dia"] = df_ventana["_dt"].dt.strftime("%Y-%m-%d")
    df_ventana["_total_num"] = pd.to_numeric(df_ventana[cols["total"]], errors="coerce").fillna(0)
    if cols.get("ganancia"):
        df_ventana["_gan_num"] = pd.to_numeric(df_ventana[cols["ganancia"]], errors="coerce").fillna(0)
    return {"df": df_ventana, "cols": cols, "ultimo": ultimo, "nombre": nombre}


def _ventas_por_dia(df):
    """Serie: fecha -> total vendido ese día."""
    return df.groupby("_dia")["_total_num"].sum().sort_index()


def generar_alertas(carpeta, dias_ventana=30):
    """
    Devuelve lista de alertas reales. Conservador: solo salta lo claramente anómalo.
    Cada alerta: {tipo, nivel, titulo, detalle, valor}
    nivel: 'positivo' | 'atencion' | 'info'
    """
    datos = _preparar_ventas(carpeta, dias_ventana)
    if datos is None:
        return {"error": "no_ventas"}

    df = datos["df"]
    cols = datos["cols"]
    ultimo = datos["ultimo"]
    alertas = []

    ventas_dia = _ventas_por_dia(df)
    dias_con_datos = len(ventas_dia)

    # Necesitamos un mínimo de historia para que las comparaciones tengan sentido
    if dias_con_datos < 5:
        return {"alertas": [], "periodo": dias_ventana, "dias_analizados": dias_con_datos, "suficiente": False}

    ultimo_str = ultimo.strftime("%Y-%m-%d")

    # ── El último día suele estar INCOMPLETO (sincronización a mitad del día).
    #    Para no disparar falsas alarmas ("caíste 73%" por un día a medias),
    #    las comparaciones de anomalía se hacen sobre días CERRADOS (sin el último).
    #    El último día se reporta aparte, con aviso de que puede estar en curso.
    fechas_ordenadas = list(ventas_dia.index)
    dia_en_curso = ultimo_str
    total_dia_en_curso = float(ventas_dia.get(ultimo_str, 0))

    # df y series SIN el último día, para todas las comparaciones
    df_cerrados = df[df["_dia"] != ultimo_str].copy()
    ventas_cerrados = ventas_dia.drop(ultimo_str) if ultimo_str in ventas_dia.index else ventas_dia
    if len(ventas_cerrados) < 4:
        # Sin suficientes días cerrados para comparar con rigor
        return {
            "alertas": [], "periodo": dias_ventana, "dias_analizados": dias_con_datos,
            "suficiente": False, "ultimo_dia": ultimo_str
        }

    # El "día de referencia" para anomalías es ahora el último día CERRADO
    ref = pd.to_datetime(ventas_cerrados.index[-1])
    ref_str = ref.strftime("%Y-%m-%d")

    # ── ALERTA 1: Último día cerrado vs mismos días de la semana ──
    dow_ref = ref.weekday()
    mismos_dow = df_cerrados[df_cerrados["_dt"].dt.weekday == dow_ref]
    ventas_mismos_dow = mismos_dow.groupby("_dia")["_total_num"].sum()
    if ref_str in ventas_mismos_dow.index and len(ventas_mismos_dow) >= 3:
        total_ref = ventas_mismos_dow[ref_str]
        otros = ventas_mismos_dow.drop(ref_str)
        promedio_otros = otros.mean()
        if promedio_otros > 0:
            cambio = (total_ref - promedio_otros) / promedio_otros * 100
            if cambio <= -25:
                alertas.append({
                    "tipo": "dia_bajo", "nivel": "atencion",
                    "titulo": f"El último {DIAS_ES[dow_ref]} vendió por debajo de lo habitual",
                    "detalle": f"Vendiste ${total_ref:,.0f}, alrededor de un {abs(cambio):.0f}% menos que tus otros {DIAS_ES[dow_ref]} recientes (promedio ${promedio_otros:,.0f}).",
                    "valor": round(total_ref, 2)
                })
            elif cambio >= 30:
                alertas.append({
                    "tipo": "dia_alto", "nivel": "positivo",
                    "titulo": f"El último {DIAS_ES[dow_ref]} vendió por encima de lo habitual",
                    "detalle": f"Vendiste ${total_ref:,.0f}, alrededor de un {cambio:.0f}% más que tus otros {DIAS_ES[dow_ref]} recientes (promedio ${promedio_otros:,.0f}). Vale la pena ver qué pasó ese día.",
                    "valor": round(total_ref, 2)
                })

    # ── ALERTA 2: Tendencia reciente (7 días cerrados vs 7 anteriores) ──
    cerrados_ord = list(ventas_cerrados.index)
    if len(cerrados_ord) >= 14:
        ult7 = ventas_cerrados[cerrados_ord[-7:]].sum()
        prev7 = ventas_cerrados[cerrados_ord[-14:-7]].sum()
        if prev7 > 0:
            cambio = (ult7 - prev7) / prev7 * 100
            if cambio <= -20:
                alertas.append({
                    "tipo": "tendencia_baja", "nivel": "atencion",
                    "titulo": "Tus ventas vienen bajando esta última semana",
                    "detalle": f"En los últimos 7 días cerrados vendiste ${ult7:,.0f}, un {abs(cambio):.0f}% menos que los 7 días anteriores (${prev7:,.0f}). Conviene estar atento.",
                    "valor": round(ult7, 2)
                })
            elif cambio >= 20:
                alertas.append({
                    "tipo": "tendencia_alta", "nivel": "positivo",
                    "titulo": "Tus ventas vienen subiendo esta última semana",
                    "detalle": f"En los últimos 7 días cerrados vendiste ${ult7:,.0f}, un {cambio:.0f}% más que los 7 días anteriores (${prev7:,.0f}). Buen momento.",
                    "valor": round(ult7, 2)
                })

    # ── ALERTA 3: Mejor día del periodo (sobre días cerrados) ──
    if len(ventas_cerrados) >= 7:
        mejor_dia = ventas_cerrados.idxmax()
        mejor_val = ventas_cerrados.max()
        prom = ventas_cerrados.mean()
        if prom > 0 and mejor_val >= prom * 1.5:
            dt = pd.to_datetime(mejor_dia)
            alertas.append({
                "tipo": "mejor_dia", "nivel": "info",
                "titulo": "Tu mejor día de este periodo",
                "detalle": f"El {dt.day} de {['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'][dt.month-1]} ({DIAS_ES[dt.weekday()]}) vendiste ${mejor_val:,.0f}, tu cifra más alta del periodo.",
                "valor": round(mejor_val, 2)
            })

    # ── ALERTA 4: Margen reciente vs promedio (sobre días cerrados) ──
    if "_gan_num" in df_cerrados.columns and len(ventas_cerrados) >= 10:
        df_cerrados["_dt_norm"] = df_cerrados["_dt"].dt.normalize()
        corte_reciente = ref - pd.Timedelta(days=6)
        reciente = df_cerrados[df_cerrados["_dt_norm"] >= corte_reciente]
        anterior = df_cerrados[df_cerrados["_dt_norm"] < corte_reciente]
        def _margen(sub):
            t = sub["_total_num"].sum()
            g = sub["_gan_num"].sum()
            return (g / t * 100) if t > 0 else None
        m_rec = _margen(reciente)
        m_ant = _margen(anterior)
        if m_rec is not None and m_ant is not None and m_ant > 0:
            dif = m_rec - m_ant
            if dif <= -3:
                alertas.append({
                    "tipo": "margen_baja", "nivel": "atencion",
                    "titulo": "Tu margen bajó en los últimos días",
                    "detalle": f"Tu margen de los últimos 7 días fue {m_rec:.1f}%, frente a {m_ant:.1f}% del resto del periodo. Puede ser por cambios en precios, costos o en qué productos se vendieron.",
                    "valor": round(m_rec, 2)
                })

    return {
        "alertas": alertas,
        "periodo": dias_ventana,
        "dias_analizados": dias_con_datos,
        "suficiente": True,
        "ultimo_dia": ultimo_str,
        "dia_en_curso": {"fecha": dia_en_curso, "total": round(total_dia_en_curso, 2)},
    }
