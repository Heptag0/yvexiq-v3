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
                import requests
                config = cc()
                auto_sync_ids = config.get("auto_sync", [])
                token = config.get("token")
                total = 0
                
                if token and auto_sync_ids:
                    try:
                        res = requests.get(
                            "https://yvexiq.com/api/conexiones",
                            headers={"Authorization": f"Bearer {token}"}
                        )
                        if res.status_code == 200:
                            conexiones = {c["id"]: c for c in res.json()}
                            for conexion_id in auto_sync_ids:
                                if conexion_id in conexiones:
                                    from core.sync import re_extraer_y_sincronizar
                                    resultado = re_extraer_y_sincronizar(conexiones[conexion_id])
                                    if resultado["ok"]:
                                        total += resultado["archivos"]
                    except:
                        pass
                
                if self.callback_estado:
                    self.callback_estado({"ok": True, "archivos": total})