"""DAO (Data Access Object): los contratos de acceso a datos de las metas.

El servicio, la API y las pantallas solo conocen estas interfaces. Quién las cumple (SQLAlchemy contra
PostgreSQL, o una versión en memoria para las pruebas) lo decide la fábrica (fabrica.py).
Todos devuelven DTO, nunca objetos del ORM: así nadie fuera de dao/ toca la sesión de la base de datos.
"""
from abc import ABC, abstractmethod


class TiendaDAO(ABC):

    @abstractmethod
    def listar_activas(self):
        """[TiendaDTO] de las tiendas activas, ordenadas por código."""

    @abstractmethod
    def obtener(self, tienda_id):
        """TiendaDTO o None si no existe o no está activa."""


class MetaDAO(ABC):

    @abstractmethod
    def listar_periodo(self, anio, mes):
        """[MetaDTO] de un mes."""

    @abstractmethod
    def obtener(self, meta_id):
        """MetaDTO o None."""

    @abstractmethod
    def buscar(self, tienda_id, anio, mes):
        """La MetaDTO de esa tienda en ese mes, o None."""

    @abstractmethod
    def crear(self, entrada, usuario):
        """Guarda una MetaEntradaDTO ya validada y devuelve la MetaDTO creada."""

    @abstractmethod
    def actualizar(self, meta_id, entrada, usuario):
        """Cambia valor y nota; devuelve la MetaDTO actualizada (o None si no existe)."""

    @abstractmethod
    def eliminar(self, meta_id):
        """True si la borró."""


class HistorialDAO(ABC):

    @abstractmethod
    def registrar(self, meta_id, tienda_id, anio, mes, accion, valor_anterior, valor_nuevo, usuario):
        """Guarda un cambio de una meta."""

    @abstractmethod
    def listar(self, meta_id):
        """[HistorialDTO] del más reciente al más antiguo."""


class VentaDAO(ABC):

    @abstractmethod
    def ventas_del_mes(self, anio, mes):
        """{tienda_id: VentaMesDTO} con la venta acumulada de cada tienda en ese mes."""
