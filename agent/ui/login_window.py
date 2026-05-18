# agent/ui/login_window.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFrame)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont
from core.auth import login

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
        self.setFixedSize(400, 500)
        self.worker = None
        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(0)

        # Logo
        logo = QLabel("Y")
        logo.setAlignment(Qt.AlignCenter)
        logo.setObjectName("logo")
        layout.addWidget(logo)

        # Título
        titulo = QLabel("YvexIQ")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setObjectName("titulo")
        layout.addWidget(titulo)

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
            #logo {
                font-size: 36px;
                font-weight: bold;
                color: white;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7c22d4, stop:1 #9333ea);
                border-radius: 16px;
                padding: 12px;
                max-width: 60px;
                min-width: 60px;
                max-height: 60px;
                min-height: 60px;
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
        """)