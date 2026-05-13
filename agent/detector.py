import os

def buscar_archivos():
    encontrados = []
    carpetas_comunes = [
        "C:/Users",
        "C:/Program Files",
        "C:/Program Files (x86)"
    ]
    rutas_excluidas = [
    "miniconda", "AppData", "node_modules", 
    "site-packages", "Firebird_2_5"
    ]
    for carpeta in carpetas_comunes:
        for ruta, carpetas, archivos in os.walk(carpeta):
            for archivo in archivos:
                if archivo.lower().endswith(".csv") or archivo.lower().endswith(".fdb") or archivo.lower().endswith(".xlsx"):
                    if any(ruta_excluida in ruta for ruta_excluida in rutas_excluidas):
                        continue
                    ruta_completa = os.path.join(ruta, archivo)
                    if os.path.getsize(ruta_completa) > 10240:
                        encontrados.append(os.path.join(ruta, archivo))
    if not encontrados:
        ruta_manual = input("No se encontraron archivos. Ingresa la ruta manualmente: ")
        if os.path.exists(ruta_manual):
            encontrados.append(ruta_manual)
    return encontrados


