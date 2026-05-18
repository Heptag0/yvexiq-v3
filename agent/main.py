import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from core.auth import esta_autenticado
from core.config import cargar_config
from ui.login_window import LoginWindow
from ui.onboarding import OnboardingWindow
from ui.main_window import MainWindow

class YvexIQApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        from PySide6.QtCore import Qt
        self.app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
        self.app.setFont(QFont("Tahoma", 10, QFont.Weight.Normal))
        self.app.setQuitOnLastWindowClosed(False)
        self.ventana = None
        self._onboarding_temporal = None

    def mostrar_login(self):
        self.ventana = LoginWindow()
        self.ventana.login_exitoso.connect(self.post_login)
        self.ventana.show()

    def post_login(self):
        self.ventana.close()
        config = cargar_config()
        if config.get("conexion_id") and config.get("carpeta_csvs"):
            self.mostrar_principal()
        else:
            self.mostrar_onboarding()

    def mostrar_onboarding(self):
        if isinstance(self.ventana, MainWindow):
            self.ventana.hide()
        ventana_onboarding = OnboardingWindow()
        ventana_onboarding.configuracion_lista.connect(self._volver_a_principal)
        ventana_onboarding.show()
        self._onboarding_temporal = ventana_onboarding

    def _volver_a_principal(self):
        self._onboarding_temporal.close()
        if isinstance(self.ventana, MainWindow):
            self.ventana._cargar_conexiones()
            self.ventana.show()
        else:
            self.mostrar_principal()

    def mostrar_principal(self):
        if isinstance(self.ventana, OnboardingWindow):
            self.ventana.close()
        self.ventana = MainWindow()
        self.ventana.cerrar_sesion.connect(self.mostrar_login)
        self.ventana.ir_a_onboarding.connect(self.mostrar_onboarding)
        self.ventana.show()

    def ejecutar(self):
        if esta_autenticado():
            config = cargar_config()
            if config.get("conexion_id") and config.get("carpeta_csvs"):
                self.mostrar_principal()
            else:
                self.mostrar_onboarding()
        else:
            self.mostrar_login()

        sys.exit(self.app.exec())

if __name__ == "__main__":
    try:
        yvex = YvexIQApp()
        yvex.ejecutar()
    except Exception as e:
        import traceback
        traceback.print_exc()
        input("Presiona Enter para cerrar...")