from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QComboBox, QProgressBar, QSystemTrayIcon, QMenu, QScrollArea, QMessageBox)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont
from core.config import cargar_config, guardar_config
from core.auth import logout, get_token
from core.sync import sincronizar
from core.scheduler import Scheduler
from datetime import datetime
import requests
import os
from core.sync import sincronizar_todas

API_URL = "https://yvexiq.com/api"


class SyncWorker(QThread):
    progreso = Signal(int)
    terminado = Signal(dict)

    def __init__(self, conexion_id=None, carpeta=None):
        super().__init__()
        self.conexion_id = conexion_id
        self.carpeta = carpeta

    def run(self):
        if self.conexion_id and self.carpeta:
            resultado = sincronizar(
                conexion_id=self.conexion_id,
                carpeta=self.carpeta,
                callback=lambda p: self.progreso.emit(p)
            )
        else:
            resultado = sincronizar_todas(callback=lambda p: self.progreso.emit(p))
        self.terminado.emit(resultado)


class ReExtractWorker(QThread):
    progreso = Signal(int)
    terminado = Signal(dict)

    def __init__(self, conexion):
        super().__init__()
        self.conexion = conexion

    def run(self):
        from core.sync import re_extraer_y_sincronizar
        resultado = re_extraer_y_sincronizar(
            self.conexion,
            callback=lambda p: self.progreso.emit(p)
        )
        self.terminado.emit(resultado)


class ConexionCard(QFrame):
    activada = Signal(dict)
    eliminada = Signal(int)
    sincronizar_individual = Signal(dict)
    auto_sync_cambiado = Signal(int, bool)

    def __init__(self, conexion: dict, activa: bool = False, auto_sync: bool = False):
        super().__init__()
        self.conexion = conexion
        self.setObjectName("card_activa" if activa else "card")
        self.setCursor(Qt.PointingHandCursor)
        self._setup_ui(activa, auto_sync)

    def _get_icono(self):
        tipo = self.conexion.get("tipo_bd", "").lower()
        if tipo == "fdb":
            return "🗄️"
        elif tipo == "xlsx":
            return "📊"
        else:
            return "📄"

    def _setup_ui(self, activa, auto_sync):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)

        nombre = self.conexion.get("nombre", "Sin nombre")
        tipo = self.conexion.get("tipo_bd", "").upper()
        icono = self._get_icono()

        label_nombre = QLabel(f"{icono} {nombre}")
        label_nombre.setObjectName("card_titulo")

        ultima_sync = self.conexion.get("fecha_ultima_sincronizacion")
        if ultima_sync:
            label_sync = QLabel(f"{tipo} · Sync: {ultima_sync[:10]}")
        else:
            label_sync = QLabel(f"{tipo} · Sin sincronizar")
        label_sync.setObjectName("label_dim")

        info_layout.addWidget(label_nombre)
        info_layout.addWidget(label_sync)
        layout.addLayout(info_layout)
        layout.addStretch()

        btn_auto = QPushButton("⚙ Auto")
        btn_auto.setObjectName("btn_auto_on" if auto_sync else "btn_auto_off")
        btn_auto.setFixedHeight(26)
        btn_auto.setCheckable(True)
        btn_auto.setChecked(auto_sync)
        btn_auto.clicked.connect(lambda checked: self._toggle_auto(checked, btn_auto))
        layout.addWidget(btn_auto)

        btn_sync = QPushButton("⟳")
        btn_sync.setObjectName("btn_ghost")
        btn_sync.setFixedSize(34, 28)
        btn_sync.clicked.connect(lambda: self.sincronizar_individual.emit(self.conexion))
        layout.addWidget(btn_sync)

        btn_eliminar = QPushButton("✕")
        btn_eliminar.setObjectName("btn_eliminar")
        btn_eliminar.setFixedSize(28, 28)
        btn_eliminar.clicked.connect(lambda: self.eliminada.emit(self.conexion["id"]))
        layout.addWidget(btn_eliminar)

    def _toggle_auto(self, checked, btn):
        btn.setObjectName("btn_auto_on" if checked else "btn_auto_off")
        btn.style().unpolish(btn)
        btn.style().polish(btn)
        self.auto_sync_cambiado.emit(self.conexion["id"], checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.activada.emit(self.conexion)


class MainWindow(QWidget):
    cerrar_sesion = Signal()
    ir_a_onboarding = Signal()

    def __init__(self):
        super().__init__()
        self.setFont(QFont("Tahoma", 10, QFont.Weight.Normal))
        self.setWindowTitle("YvexIQ")
        self.setFixedSize(480, 620)
        self.sync_worker = None
        self.conexiones = []
        self.scheduler = Scheduler(callback_estado=self._on_sync_automatico)
        self._setup_ui()
        self._apply_styles()
        self._setup_tray()
        self._cargar_estado()
        self._cargar_conexiones()
        self.scheduler.iniciar()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        header = QHBoxLayout()
        logo = QLabel("Y")
        logo.setObjectName("logo")
        titulo = QLabel("YvexIQ")
        titulo.setObjectName("titulo")
        header.addWidget(logo)
        header.addWidget(titulo)
        header.addStretch()
        config = cargar_config()
        email = config.get("email", "")
        label_email = QLabel(email)
        label_email.setObjectName("label_dim")
        header.addWidget(label_email)
        btn_logout = QPushButton("Cerrar sesión")
        btn_logout.setObjectName("btn_ghost")
        btn_logout.clicked.connect(self._logout)
        header.addWidget(btn_logout)
        layout.addLayout(header)

        card_sync = QFrame()
        card_sync.setObjectName("card")
        sl = QVBoxLayout(card_sync)
        sl.setContentsMargins(18, 14, 18, 14)
        sl.setSpacing(10)

        self.label_ultima_sync = QLabel("Última sincronización: nunca")
        self.label_ultima_sync.setObjectName("label_dim")
        sl.addWidget(self.label_ultima_sync)

        self.progress = QProgressBar()
        self.progress.setObjectName("progress")
        self.progress.setValue(0)
        self.progress.hide()
        sl.addWidget(self.progress)

        self.label_sync_estado = QLabel("")
        self.label_sync_estado.setObjectName("label_dim")
        self.label_sync_estado.hide()
        sl.addWidget(self.label_sync_estado)

        self.btn_sync = QPushButton("⟳  Sincronizar todas")
        self.btn_sync.setObjectName("btn_primary")
        self.btn_sync.clicked.connect(self._sincronizar)
        sl.addWidget(self.btn_sync)

        layout.addWidget(card_sync)

        card_intervalo = QFrame()
        card_intervalo.setObjectName("card")
        il = QHBoxLayout(card_intervalo)
        il.setContentsMargins(18, 12, 18, 12)
        il.setSpacing(10)

        label_intervalo = QLabel("Sync automática")
        label_intervalo.setObjectName("label_seccion")
        il.addWidget(label_intervalo)
        il.addStretch()

        self.combo_intervalo = QComboBox()
        self.combo_intervalo.setObjectName("combo")
        self.combo_intervalo.addItems(["1h", "2h", "4h", "8h", "24h"])
        self.combo_intervalo.setCurrentIndex(2)
        self.combo_intervalo.setFixedWidth(80)
        self.combo_intervalo.currentIndexChanged.connect(self._cambiar_intervalo)
        il.addWidget(self.combo_intervalo)

        layout.addWidget(card_intervalo)

        header_conexiones = QHBoxLayout()
        label_conexiones = QLabel("Bases de datos")
        label_conexiones.setObjectName("label_seccion")
        header_conexiones.addWidget(label_conexiones)
        header_conexiones.addStretch()

        btn_agregar = QPushButton("+ Añadir")
        btn_agregar.setObjectName("btn_ghost")
        btn_agregar.clicked.connect(self._agregar_conexion)
        header_conexiones.addWidget(btn_agregar)
        layout.addLayout(header_conexiones)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("scroll")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        self.contenedor_conexiones = QWidget()
        self.layout_conexiones = QVBoxLayout(self.contenedor_conexiones)
        self.layout_conexiones.setSpacing(8)
        self.layout_conexiones.setContentsMargins(0, 0, 0, 0)
        self.layout_conexiones.addStretch()

        scroll.setWidget(self.contenedor_conexiones)
        layout.addWidget(scroll)

    def _cargar_conexiones(self):
        token = get_token()
        if not token:
            return
        try:
            res = requests.get(
                f"{API_URL}/conexiones",
                headers={"Authorization": f"Bearer {token}"}
            )
            if res.status_code == 200:
                self.conexiones = res.json()
                self._renderizar_conexiones()
        except:
            pass

    def _renderizar_conexiones(self):
        while self.layout_conexiones.count() > 1:
            item = self.layout_conexiones.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        config = cargar_config()
        conexion_activa_id = config.get("conexion_id")
        auto_sync_ids = config.get("auto_sync", [])

        for conexion in self.conexiones:
            activa = conexion["id"] == conexion_activa_id
            auto_sync = conexion["id"] in auto_sync_ids
            card = ConexionCard(conexion, activa, auto_sync)
            card.activada.connect(self._activar_conexion)
            card.eliminada.connect(self._eliminar_conexion)
            card.sincronizar_individual.connect(self._sincronizar_individual)
            card.auto_sync_cambiado.connect(self._toggle_auto_sync)
            self.layout_conexiones.insertWidget(
                self.layout_conexiones.count() - 1, card
            )

    def _activar_conexion(self, conexion: dict):
        guardar_config({"conexion_id": conexion["id"]})
        self._renderizar_conexiones()

    def _eliminar_conexion(self, conexion_id: int):
        msg = QMessageBox(self)
        msg.setWindowTitle("Eliminar conexión")
        msg.setText("¿Seguro que quieres eliminar esta conexión?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        if msg.exec() != QMessageBox.Yes:
            return

        token = get_token()
        try:
            res = requests.delete(
                f"{API_URL}/conexiones/{conexion_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            if res.status_code == 200:
                config = cargar_config()
                if config.get("conexion_id") == conexion_id:
                    guardar_config({"conexion_id": None})
                self._cargar_conexiones()
        except:
            pass

    def _agregar_conexion(self):
        self.ir_a_onboarding.emit()

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setToolTip("YvexIQ")
        menu = QMenu()
        menu.addAction("Abrir", self.show)
        menu.addAction("Sincronizar ahora", self._sincronizar)
        menu.addSeparator()
        menu.addAction("Cerrar", self._cerrar_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self.show() if r == QSystemTrayIcon.DoubleClick else None
        )
        self.tray.show()

    def _cargar_estado(self):
        config = cargar_config()
        ultima = config.get("ultima_sincronizacion")
        if ultima:
            self.label_ultima_sync.setText(f"Última sincronización: {ultima}")
        intervalo = config.get("intervalo_horas", 4)
        opciones = [1, 2, 4, 8, 24]
        if intervalo in opciones:
            self.combo_intervalo.setCurrentIndex(opciones.index(intervalo))

    def _cambiar_intervalo(self, index):
        opciones = [1, 2, 4, 8, 24]
        guardar_config({"intervalo_horas": opciones[index]})

    def _sincronizar(self):
        if self.sync_worker and self.sync_worker.isRunning():
            return
        self.btn_sync.setEnabled(False)
        self.btn_sync.setText("Sincronizando...")
        self.progress.setValue(0)
        self.progress.show()
        self.label_sync_estado.hide()

        self.sync_worker = SyncWorker()
        self.sync_worker.progreso.connect(self.progress.setValue)
        self.sync_worker.terminado.connect(self._on_sync_terminado)
        self.sync_worker.start()

    def _on_sync_terminado(self, resultado):
        self.btn_sync.setEnabled(True)
        self.btn_sync.setText("⟳  Sincronizar todas")
        self.progress.hide()
        ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
        if resultado["ok"]:
            guardar_config({"ultima_sincronizacion": ahora})
            self.label_ultima_sync.setText(f"Última sincronización: {ahora}")
            self.label_sync_estado.setText(f"✓ {resultado['archivos']} archivos sincronizados")
        else:
            self.label_sync_estado.setText(f"✗ {resultado['error']}")
        self.label_sync_estado.show()
        self._cargar_conexiones()

    def _on_sync_automatico(self, resultado):
        ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
        if resultado["ok"]:
            guardar_config({"ultima_sincronizacion": ahora})
            self.label_ultima_sync.setText(f"Última sincronización: {ahora}")

    def _logout(self):
        self.scheduler.detener()
        logout()
        self.tray.hide()
        self.close()
        self.cerrar_sesion.emit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "YvexIQ", "Sigue corriendo en segundo plano",
            QSystemTrayIcon.Information, 2000
        )

    def _toggle_auto_sync(self, conexion_id: int, activo: bool):
        config = cargar_config()
        auto_sync = config.get("auto_sync", [])
        if activo and conexion_id not in auto_sync:
            auto_sync.append(conexion_id)
        elif not activo and conexion_id in auto_sync:
            auto_sync.remove(conexion_id)
        guardar_config({"auto_sync": auto_sync})

    def _sincronizar_individual(self, conexion: dict):
        self.btn_sync.setEnabled(False)
        self.progress.setValue(0)
        self.progress.show()
        self.label_sync_estado.hide()

        self.sync_worker = ReExtractWorker(conexion)
        self.sync_worker.progreso.connect(self.progress.setValue)
        self.sync_worker.terminado.connect(self._on_sync_terminado)
        self.sync_worker.start()

    def _cerrar_app(self):
        self.scheduler.detener()
        self.tray.hide()
        from PySide6.QtWidgets import QApplication
        QApplication.quit()

    def _apply_styles(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #08091a;
                color: #f5f3ff;
                font-family: Tahoma, sans-serif;
                font-size: 13px;
            }
            #logo {
                font-size: 18px;
                font-weight: bold;
                color: white;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7c22d4, stop:1 #9333ea);
                border-radius: 10px;
                padding: 6px 10px;
            }
            #titulo {
                font-size: 17px;
                font-weight: bold;
                color: #f5f3ff;
            }
            #card {
                background: rgba(255,255,255,0.055);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 14px;
            }
            #card_activa {
                background: rgba(147,51,234,0.12);
                border: 1px solid rgba(147,51,234,0.5);
                border-radius: 14px;
            }
            #card_titulo {
                font-size: 13px;
                font-weight: 600;
                color: #f5f3ff;
            }
            #label_seccion {
                font-size: 13px;
                font-weight: 600;
                color: #f5f3ff;
            }
            #label_dim {
                font-size: 11px;
                color: rgba(245,243,255,0.55);
            }
            QPushButton#btn_primary {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7c22d4, stop:1 #c026d3);
                border: none;
                border-radius: 10px;
                padding: 10px;
                color: white;
                font-family: Tahoma, sans-serif;
                font-size: 13px;
                font-weight: bold;
                min-height: 20px;
            }
            QPushButton#btn_primary:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #9333ea, stop:1 #d946ef);
            }
            QPushButton#btn_primary:disabled { opacity: 0.6; }
            QPushButton#btn_ghost {
                background: transparent;
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 8px;
                padding: 6px 12px;
                color: rgba(245,243,255,0.55);
                font-family: Tahoma, sans-serif;
                font-size: 12px;
                min-height: 18px;
            }
            QPushButton#btn_ghost:hover {
                border-color: rgba(255,255,255,0.3);
                color: #f5f3ff;
            }
            QPushButton#btn_eliminar {
                background: transparent;
                border: 1px solid rgba(251,113,133,0.3);
                border-radius: 6px;
                color: rgba(251,113,133,0.7);
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton#btn_eliminar:hover {
                background: rgba(251,113,133,0.1);
                border-color: rgba(251,113,133,0.6);
                color: #fb7185;
            }
            QPushButton#btn_auto_on {
                background: rgba(147,51,234,0.3);
                border: 1px solid rgba(147,51,234,0.6);
                border-radius: 6px;
                color: #c084fc;
                font-size: 11px;
                padding: 4px 8px;
            }
            QPushButton#btn_auto_off {
                background: transparent;
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 6px;
                color: rgba(245,243,255,0.4);
                font-size: 11px;
                padding: 4px 8px;
            }
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: rgba(255,255,255,0.03);
                width: 4px;
                border-radius: 2px;
            }
            QScrollBar::handle:vertical {
                background: rgba(147,51,234,0.4);
                border-radius: 2px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QProgressBar {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 6px;
                height: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7c22d4, stop:1 #c026d3);
                border-radius: 6px;
            }
            QComboBox {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 8px;
                padding: 6px 10px;
                color: #f5f3ff;
                font-family: Tahoma, sans-serif;
                font-size: 12px;
            }
            QComboBox:hover { border-color: #9333ea; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #0f1030;
                border: 1px solid rgba(255,255,255,0.1);
                color: #f5f3ff;
                selection-background-color: rgba(147,51,234,0.3);
            }
            QMessageBox {
                background-color: #08091a;
                color: #f5f3ff;
            }
        """)