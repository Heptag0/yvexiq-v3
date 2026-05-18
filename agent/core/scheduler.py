import threading
import time
from core.sync import sincronizar
from core.config import cargar_config
import os

class Scheduler:
    def __init__(self, callback_sync=None, callback_estado=None):
        self.callback_sync = callback_sync
        self.callback_estado = callback_estado
        self._hilo = None
        self._corriendo = False

    def iniciar(self):
        if self._corriendo:
            return
        self._corriendo = True
        self._hilo = threading.Thread(target=self._loop, daemon=True)
        self._hilo.start()

    def detener(self):
        self._corriendo = False

    def _loop(self):
        while self._corriendo:
            intervalo_horas = cargar_config().get("intervalo_horas", 4)
            intervalo_segundos = intervalo_horas * 3600
            tiempo_espera = 0

            while tiempo_espera < intervalo_segundos and self._corriendo:
                time.sleep(1)
                tiempo_espera += 1

            if self._corriendo:
                from core.config import cargar_config as cc
                config = cc()
                auto_sync_ids = config.get("auto_sync", [])
                temp_base = os.path.join(os.path.expanduser("~"), ".yvexiq", "temp")

                total = 0
                for conexion_id in auto_sync_ids:
                    carpeta = os.path.join(temp_base, str(conexion_id))
                    if os.path.exists(carpeta):
                        from core.sync import sincronizar
                        res = sincronizar(conexion_id, carpeta)
                        if res["ok"]:
                            total += res["archivos"]

                if self.callback_estado:
                    self.callback_estado({"ok": True, "archivos": total})