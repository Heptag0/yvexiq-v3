from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem, QFrame, QProgressBar)
from PySide6.QtCore import Qt, Signal, QThread
from core.config import guardar_config
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from detector import buscar_archivos
from analyzer import puntuar_archivos
from table_analyzer import analizar_tablas
from extractor import extraer_tablas
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QFileDialog, QListWidgetItem
from core.auth import get_token
import requests


class DetectorWorker(QThread):
    resultado = Signal(list)

    def run(self):
        archivos = buscar_archivos()
        resultados = puntuar_archivos(archivos)
        self.resultado.emit(resultados[:10])


class ExtractorWorker(QThread):
    terminado = Signal(str)

    def __init__(self, archivo, conexion_id):
        super().__init__()
        self.archivo = archivo
        self.conexion_id = conexion_id

    def run(self):
        if self.archivo.lower().endswith(".fdb"):
            tablas = analizar_tablas(self.archivo)
        else:
            tablas = None
        carpeta = extraer_tablas(self.archivo, tablas, self.conexion_id)
        self.terminado.emit(carpeta)


class OnboardingWindow(QWidget):
    configuracion_lista = Signal()

    def __init__(self):
        super().__init__()
        from PySide6.QtGui import QFont
        font = QFont("Segoe UI", 10)
        self.setFont(font)
        self.setWindowTitle("YvexIQ — Añadir bases de datos")
        self.setFixedSize(500, 640)
        self.archivos = []
        self.worker = None
        self._setup_ui()
        self._apply_styles()
        self._detectar_archivos()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(16)

        # Título
        titulo = QLabel("Añade tu base de datos")
        titulo.setObjectName("titulo")
        layout.addWidget(titulo)

        subtitulo = QLabel("Detectando bases de datos en tu equipo...")
        subtitulo.setObjectName("subtitulo")
        subtitulo.setWordWrap(True)
        layout.addWidget(subtitulo)
        self.label_subtitulo = subtitulo

        # Progress bar (visible durante detección)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # modo indeterminado
        self.progress.setObjectName("progress")
        layout.addWidget(self.progress)

        # Card con lista de archivos
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)

        label_lista = QLabel("Selecciona tu base de datos principal:")
        label_lista.setObjectName("label_lista")
        card_layout.addWidget(label_lista)

        self.lista = QListWidget()
        self.lista.setObjectName("lista")
        self.lista.hide()
        card_layout.addWidget(self.lista)

        card.hide()
        self.card = card
        layout.addWidget(card)

        # Estado de extracción
        self.label_estado = QLabel("")
        self.label_estado.setObjectName("subtitulo")
        self.label_estado.setWordWrap(True)
        self.label_estado.hide()
        layout.addWidget(self.label_estado)

        # Botón manual
        self.btn_manual = QPushButton("📁  Añadir manualmente")
        self.btn_manual.setObjectName("btn_ghost")
        self.btn_manual.clicked.connect(self._seleccionar_manual)
        layout.addWidget(self.btn_manual)

        # Botón confirmar
        self.btn_confirmar = QPushButton("Confirmar selección")
        self.btn_confirmar.setObjectName("btn_primary")
        self.btn_confirmar.clicked.connect(self._confirmar)
        self.btn_confirmar.hide()
        layout.addWidget(self.btn_confirmar)

        btn_omitir = QPushButton("Omitir por ahora")
        btn_omitir.setObjectName("btn_ghost")
        btn_omitir.clicked.connect(self._omitir)
        layout.addWidget(btn_omitir)

        layout.addStretch()

    def _detectar_archivos(self):
        self.worker = DetectorWorker()
        self.worker.resultado.connect(self._on_deteccion)
        self.worker.start()

    def _on_deteccion(self, resultados):
        self.archivos = resultados
        self.progress.hide()

        if not resultados:
            self.label_subtitulo.setText("No se encontraron bases de datos. Asegúrate de que tu software de gestión está instalado.")
            return

        self.label_subtitulo.setText("Selecciona cuál es tu base de datos principal:")
        self.card.show()
        self.lista.show()

        for puntuacion, ruta in resultados:
            nombre = os.path.basename(ruta)
            item = QListWidgetItem(f"{nombre}\n{ruta}")
            item.setData(Qt.UserRole, ruta)
            self.lista.addItem(item)

        self.lista.setCurrentRow(0)
        self.btn_confirmar.show()

    def _confirmar(self):
        item = self.lista.currentItem()
        if not item:
            return

        ruta = item.data(Qt.UserRole)
        self.btn_confirmar.setEnabled(False)
        self.btn_confirmar.setText("Extrayendo datos...")
        self.label_estado.setText("Analizando tablas con IA, esto puede tardar unos minutos...")
        self.label_estado.show()



        API_URL = "https://yvexiq.com/api"
        token = get_token()
        nombre = os.path.basename(ruta)
        headers = {"Authorization": f"Bearer {token}"}
        res_lista = requests.get(f"{API_URL}/conexiones", headers=headers)
        conexion_id = None

        if res_lista.status_code == 200:
            for conexion in res_lista.json():
                if conexion["ruta_archivo"] == ruta:
                    conexion_id = conexion["id"]
                    break

        if not conexion_id:
            tipo = "fdb" if ruta.lower().endswith(".fdb") else "csv" if ruta.lower().endswith(".csv") else "xlsx"
            res = requests.post(
                f"{API_URL}/conexiones",
                headers=headers,
                json={"nombre": nombre, "tipo_bd": tipo, "ruta_archivo": ruta}
            )
            if res.status_code == 200:
                conexion_id = res.json()["id"]
            else:
                self.label_estado.setText("Error al registrar la conexión. Intenta de nuevo.")
                self.btn_confirmar.setEnabled(True)
                self.btn_confirmar.setText("Confirmar selección")
                return

        self.label_estado.setText("Analizando tablas con IA, esto puede tardar unos segundos...")
        self.extractor = ExtractorWorker(ruta, conexion_id)
        self.extractor.terminado.connect(lambda carpeta: self._on_extraccion(carpeta, conexion_id, ruta))
        self.extractor.start()

    def _on_extraccion(self, carpeta, conexion_id, archivo):
        guardar_config({
            "archivo_principal": archivo,
            "carpeta_csvs": carpeta,
            "conexion_id": conexion_id
        })
        self.configuracion_lista.emit()


    def _seleccionar_manual(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar base de datos",
            "",
            "Bases de datos (*.fdb *.csv *.xlsx);;Todos los archivos (*)"
        )
        if ruta:
            self.label_subtitulo.setText("Archivo seleccionado manualmente:")
            self.card.show()
            self.lista.show()
            self.lista.clear()
            nombre = os.path.basename(ruta)
            item = QListWidgetItem(f"{nombre}\n{ruta}")
            item.setData(Qt.UserRole, ruta)
            self.lista.addItem(item)
            self.lista.setCurrentRow(0)
            self.btn_confirmar.show()

    def _omitir(self):
        self.configuracion_lista.emit()

    def _apply_styles(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #08091a;
                color: #f5f3ff;
                font-family: 'Segoe UI', sans-serif;
            }
            #titulo {
                font-size: 22px;
                font-weight: bold;
                color: #f5f3ff;
            }
            #subtitulo {
                font-size: 13px;
                color: rgba(245,243,255,0.55);
            }
            #label_lista {
                font-size: 12px;
                font-weight: 600;
                color: rgba(245,243,255,0.55);
                margin-bottom: 8px;
            }
            #card {
                background: rgba(255,255,255,0.055);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 20px;
            }
            #lista {
                background: transparent;
                border: none;
                color: #f5f3ff;
                font-size: 13px;
            }
            #lista::item {
                padding: 10px;
                border-radius: 8px;
                margin: 2px 0;
            }
            #lista::item:selected {
                background: rgba(147,51,234,0.3);
                border: 1px solid rgba(147,51,234,0.5);
            }
            #lista::item:hover {
                background: rgba(255,255,255,0.05);
            }
            QProgressBar {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                height: 6px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7c22d4, stop:1 #c026d3);
                border-radius: 8px;
            }
            #btn_primary {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7c22d4, stop:1 #c026d3);
                border: none;
                border-radius: 10px;
                padding: 13px;
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            #btn_primary:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #9333ea, stop:1 #d946ef);
            }
            #btn_primary:disabled {
                opacity: 0.6;
            }
        """)
