from detector import buscar_archivos
from analyzer import puntuar_archivos

archivos = buscar_archivos()
resultados = puntuar_archivos(archivos)

print("Archivos encontrados ordenados por relevancia:")
for i, (puntuacion, ruta) in enumerate(resultados[:5], 1):
    print(f"{i}. [{puntuacion} pts] {ruta}")

mostrados = 5
respuesta = input("\n¿Cuál es tu base de datos principal? (número) o escribe 'ver mas': ")

while respuesta.lower() == "ver mas":
    for i, (puntuacion, ruta) in enumerate(resultados[mostrados:mostrados+5], mostrados+1):
        print(f"{i}. [{puntuacion} pts] {ruta}")
    mostrados += 5
    respuesta = input("\n¿Cuál es tu base de datos principal? (número) o escribe 'ver mas': ")
    if mostrados >= len(resultados):
        print("No hay más archivos disponibles.")
        respuesta = input("Ingresa el número de tu selección: ")
        break

seleccion = int(respuesta)
archivo_principal = resultados[seleccion - 1][1]
print(f"\nSeleccionado: {archivo_principal}")

from table_analyzer import analizar_tablas

tablas_relevantes = analizar_tablas(archivo_principal)
print(f"\nTablas relevantes detectadas por Claude:\n{tablas_relevantes}")

from extractor import extraer_tablas
extraer_tablas(archivo_principal, tablas_relevantes)
print("Tablas extraídas correctamente")
