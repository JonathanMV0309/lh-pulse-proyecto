"""DECORATOR: le agrega caché a cualquier TiendaDAO sin cambiarlo.

Problema: la consulta de metas (HU-05) y cada validación de una meta piden la lista de tiendas
activas, que casi nunca cambia. Repetir esa consulta en cada petición es trabajo de más para la base
de datos. Meter la caché dentro de TiendaDAOSQLAlchemy mezclaría dos responsabilidades y obligaría a
repetirla en cualquier otro DAO de tiendas.

TiendaDAOConCache cumple el mismo contrato TiendaDAO y envuelve a otro: quien lo usa no nota la
diferencia. Complejidad: los datos pueden quedar viejos hasta N segundos (por eso existe invalidar()).
"""
import threading
import time

from app.metas.dao.base import TiendaDAO


class TiendaDAOConCache(TiendaDAO):

    def __init__(self, envuelto, segundos=60, reloj=time.monotonic):
        self._envuelto = envuelto
        self._segundos = segundos
        self._reloj = reloj
        self._lista, self._vence = None, 0.0
        self._candado = threading.Lock()

    def listar_activas(self):
        with self._candado:
            if self._lista is None or self._reloj() >= self._vence:
                self._lista = self._envuelto.listar_activas()
                self._vence = self._reloj() + self._segundos
            return list(self._lista)

    def obtener(self, tienda_id):
        # Se responde desde la lista en caché; si no está ahí, se pregunta al DAO real
        encontrada = next((t for t in self.listar_activas() if t.id == tienda_id), None)
        return encontrada or self._envuelto.obtener(tienda_id)

    def invalidar(self):
        with self._candado:
            self._lista = None
