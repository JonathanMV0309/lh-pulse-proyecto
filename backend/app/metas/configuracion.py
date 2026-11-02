"""SINGLETON: la configuración del módulo de metas.

Problema: varias piezas (la fábrica de DAO, el semáforo, la caché de tiendas) necesitan los mismos
valores del .env. Si cada una lee el entorno por su cuenta, pueden quedar con valores distintos y el
.env se lee muchas veces. Con un Singleton hay una sola instancia, creada la primera vez que se pide.

Complejidad: es estado global; por eso las pruebas lo reinician con ConfiguracionMetas.reiniciar().
"""
import os
import threading


class ConfiguracionMetas:

    _instancia = None
    _candado = threading.Lock()

    def __new__(cls):
        if cls._instancia is None:
            with cls._candado:                      # gunicorn usa hilos: que solo uno la cree
                if cls._instancia is None:
                    instancia = super().__new__(cls)
                    instancia._cargar()
                    cls._instancia = instancia
        return cls._instancia

    def _cargar(self):
        self.origen_datos = os.getenv("METAS_ORIGEN_DATOS", "sqlalchemy").strip().lower()   # sqlalchemy | memoria
        self.semaforo = os.getenv("METAS_SEMAFORO", "proporcional").strip().lower()          # proporcional | mensual
        self.umbral_verde = float(os.getenv("METAS_UMBRAL_VERDE", "1.0"))
        self.umbral_amarillo = float(os.getenv("METAS_UMBRAL_AMARILLO", "0.9"))
        self.cache_tiendas_segundos = int(os.getenv("METAS_CACHE_TIENDAS_SEGUNDOS", "60"))

    @classmethod
    def reiniciar(cls):
        """Solo para pruebas: la próxima vez se vuelve a leer el entorno."""
        with cls._candado:
            cls._instancia = None
