import os

def buscar_archivos():
    encontrados = []
    carpetas_comunes = [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Documents"),
        "C:/Users",
        "C:/Program Files",
        "C:/Program Files (x86)",
        "D:/",
        "E:/"
    ]
    rutas_excluidas = [
        "miniconda", "AppData", "node_modules",
        "site-packages", "Firebird_2_5", ".git",
        "Windows", "System32"
    ]
    for carpeta in carpetas_comunes:
        if not os.path.exists(carpeta):
            continue
        for ruta, carpetas, archivos in os.walk(carpeta):
            if any(excluida in ruta for excluida in rutas_excluidas):
                continue
            for archivo in archivos:
                if archivo.lower().endswith((".csv", ".fdb", ".xlsx")):
                    ruta_completa = os.path.join(ruta, archivo)
                    try:
                        if os.path.getsize(ruta_completa) > 10240:
                            encontrados.append(ruta_completa)
                    except (PermissionError, OSError):
                        continue
    return encontrados


