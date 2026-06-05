# agent/ui/login_window.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFrame)
from PySide6.QtCore import Qt, Signal, QThread, QRect
from PySide6.QtGui import QFont, QPixmap, QLinearGradient, QColor, QPainter
from core.auth import login
import sys
import os

class GradientLabel(QLabel):
    def paintEvent(self, event):
        from PySide6.QtGui import QImage, QBrush
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        scale = 3
        font = QFont("Tahoma", 26, QFont.Weight.Bold)
        
        img = QImage(self.size() * scale, QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        
        p2 = QPainter(img)
        p2.setRenderHint(QPainter.Antialiasing)
        p2.setRenderHint(QPainter.TextAntialiasing)
        scaled_font = QFont("Tahoma", 26 * scale, QFont.Weight.Bold)
        p2.setFont(scaled_font)
        p2.setPen(QColor("white"))
        p2.drawText(img.rect(), Qt.AlignVCenter | Qt.AlignLeft, self.text())
        p2.end()
        
        gradient = QLinearGradient(0, 0, img.width(), 0)
        gradient.setColorAt(0.0, QColor("#ffffff"))
        gradient.setColorAt(0.5, QColor("#c084fc"))
        gradient.setColorAt(1.0, QColor("#a855f7"))
        
        p3 = QPainter(img)
        p3.setCompositionMode(QPainter.CompositionMode_SourceIn)
        p3.fillRect(img.rect(), QBrush(gradient))
        p3.end()
        
        from PySide6.QtGui import QPixmap
        pixmap = QPixmap.fromImage(img).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

class LoginWorker(QThread):
    resultado = Signal(dict)

    def __init__(self, email, password):
        super().__init__()
        self.email = email
        self.password = password

    def run(self):
        resultado = login(self.email, self.password)
        self.resultado.emit(resultado)


class LoginWindow(QWidget):
    login_exitoso = Signal()

    def __init__(self):
        super().__init__()
        from PySide6.QtGui import QFont
        font = QFont("Segoe UI", 10)
        self.setFont(font)
        self.setWindowTitle("YvexIQ")
        self.setFixedSize(460, 540)
        self.worker = None
        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(0)

        # Logo con icono + texto degradado
        logo_container = QHBoxLayout()
        logo_container.setAlignment(Qt.AlignCenter)
        logo_container.setSpacing(10)

        icono = QLabel()
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pixmap = QPixmap(os.path.join(base, 'yvexiq_256.png')).scaled(
            48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        icono.setPixmap(pixmap)
        icono.setStyleSheet("background: transparent; border: none;")

        texto = GradientLabel("YvexIQ")
        texto.setFixedSize(140, 45)
        texto.setObjectName("logo_texto")

        logo_container.addWidget(icono)
        logo_container.addWidget(texto)
        layout.addLayout(logo_container)
        # Subtítulo
        subtitulo = QLabel("Inicia sesión para continuar")
        subtitulo.setAlignment(Qt.AlignCenter)
        subtitulo.setObjectName("subtitulo")
        layout.addWidget(subtitulo)

        layout.addSpacing(32)

        # Card
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)
        card_layout.setContentsMargins(24, 24, 24, 24)

        # Email
        self.input_email = QLineEdit()
        self.input_email.setPlaceholderText("tu@negocio.com")
        self.input_email.setObjectName("input")

        # Password
        self.input_password = QLineEdit()
        self.input_password.setPlaceholderText("Contraseña")
        self.input_password.setEchoMode(QLineEdit.Password)
        self.input_password.setObjectName("input")
        self.input_password.returnPressed.connect(self._handle_login)

        # Error
        self.label_error = QLabel("")
        self.label_error.setObjectName("error")
        self.label_error.setWordWrap(True)
        self.label_error.hide()

        # Botón
        self.btn_login = QPushButton("Iniciar sesión")
        self.btn_login.setObjectName("btn_primary")
        self.btn_login.clicked.connect(self._handle_login)

        card_layout.addWidget(QLabel("Correo electrónico"))
        card_layout.addWidget(self.input_email)
        card_layout.addWidget(QLabel("Contraseña"))
        card_layout.addWidget(self.input_password)
        card_layout.addWidget(self.label_error)
        card_layout.addWidget(self.btn_login)
        # Enlace de registro
        registro_layout = QHBoxLayout()
        registro_layout.setAlignment(Qt.AlignCenter)
        label_registro = QLabel("¿No tienes cuenta?")
        label_registro.setObjectName("label_registro")
        btn_registro = QPushButton("Regístrate gratis")
        btn_registro.setObjectName("btn_link")
        import webbrowser
        btn_registro.clicked.connect(lambda: webbrowser.open("https://yvexiq.com/login"))
        registro_layout.addWidget(label_registro)
        registro_layout.addWidget(btn_registro)
        card_layout.addLayout(registro_layout)

        layout.addWidget(card)
        layout.addStretch()

    def _handle_login(self):
        email = self.input_email.text().strip()
        password = self.input_password.text()

        if not email or not password:
            self._mostrar_error("Completa todos los campos")
            return

        self.btn_login.setText("Iniciando sesión...")
        self.btn_login.setEnabled(False)
        self.label_error.hide()

        self.worker = LoginWorker(email, password)
        self.worker.resultado.connect(self._on_resultado)
        self.worker.start()

    def _on_resultado(self, resultado):
        self.btn_login.setText("Iniciar sesión")
        self.btn_login.setEnabled(True)

        if resultado["ok"]:
            self.login_exitoso.emit()
        else:
            self._mostrar_error(resultado["error"])

    def _mostrar_error(self, texto):
        
        self.label_error.setText(texto)
        self.label_error.show()

    def _apply_styles(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #08091a;
                color: #f5f3ff;
                font-family: Tahoma, sans-serif;
                font-size: 14px;
            }
            #logo_texto {
                font-size: 28px;
                font-weight: 700;
                color: #c084fc;
                background: transparent;
            }
            #titulo {
                font-size: 26px;
                font-weight: bold;
                color: #f5f3ff;
                margin-top: 12px;
            }
            #subtitulo {
                font-size: 13px;
                color: rgba(245,243,255,0.55);
                margin-top: 4px;
            }
            #card {
                background: rgba(255,255,255,0.055);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 20px;
            }
            QLineEdit {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 10px;
                padding: 8px 14px;
                color: #f5f3ff;
                font-family: Tahoma, sans-serif;
                font-size: 13px;
                min-height: 20px;
            }
            QLineEdit:focus {
                border: 1px solid #9333ea;
                background: rgba(147,51,234,0.09);
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
                margin-top: 6px;
            }
            QPushButton#btn_primary:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #9333ea, stop:1 #d946ef);
            }
            QPushButton#btn_primary:disabled {
                opacity: 0.6;
            }
            #error {
                color: #fb7185;
                font-size: 12px;
                background: rgba(251,113,133,0.1);
                border: 1px solid rgba(251,113,133,0.28);
                border-radius: 8px;
                padding: 8px;
            }
            QLabel {
                font-family: Tahoma, sans-serif;
                font-size: 12px;
                color: rgba(245,243,255,0.55);
                font-weight: 600;
            }
            
            QPushButton#btn_link {
                background: transparent;
                border: none;
                color: #a855f7;
                font-size: 12px;
                font-weight: 600;
                padding: 0;
                text-decoration: underline;
            }
            QPushButton#btn_link:hover { color: #d946ef; }
            #label_registro {
                font-size: 12px;
                color: rgba(245,243,255,0.45);
                font-weight: normal;
            }
        """)