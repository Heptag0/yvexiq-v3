import os

def puntuar_archivos(archivos):
    resultados = []
    palabras_clave = [
        "data", "datos", "venta", 
        "eleventa", "ventas", "pdv",
        "articulo", "articulos", "ticket", "tickets", "departamentos"
    ]
    for ruta in archivos:
        puntuacion = 0
        if ruta.lower().endswith('fdb'):
            puntuacion += 30
        if os.path.getsize(ruta) > 10240:
            puntuacion += 20
        if os.path.getsize(ruta) > 102400:
            puntuacion += 10
        if any(palabra in ruta.lower() for palabra in palabras_clave):
            puntuacion += 15
        resultados.append((puntuacion, ruta))
    return sorted(resultados, reverse=True)