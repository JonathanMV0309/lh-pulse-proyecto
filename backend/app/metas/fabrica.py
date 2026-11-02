"""ABSTRACT FACTORY: crea la familia completa de DAO que usa el módulo de metas.

Problema: el servicio necesita cuatro DAO (tiendas, metas, historial y ventas) que deben ser de la
misma «familia»: todos contra PostgreSQL en la aplicación, o todos en memoria en las pruebas. Si el
servicio los creara con `TiendaDAOSQLAlchemy()` quedaría amarrado a la base de datos y no se podría
probar sin ella; y mezclar uno en memoria con otros reales daría datos incoherentes.

Cada fábrica concreta crea su familia completa; el servicio solo conoce FabricaDAO.
Complejidad: hay que mantener una fábrica por familia y agregar el método en todas si aparece un DAO nuevo.
"""
from abc import ABC, abstractmethod

from app.metas.configuracion import ConfiguracionMetas


class FabricaDAO(ABC):

    @abstractmethod
    def crear_tienda_dao(self): ...

    @abstractmethod
    def crear_meta_dao(self): ...

    @abstractmethod
    def crear_historial_dao(self): ...

    @abstractmethod
    def crear_venta_dao(self): ...


class FabricaSQLAlchemy(FabricaDAO):
    """Familia que trabaja contra la base de datos PostgreSQL del proyecto."""

    def __init__(self):
        from app.metas.decoradores import TiendaDAOConCache
        from app.metas.dao.sqlalchemy_dao import TiendaDAOSQLAlchemy
        # Las tiendas cambian poco: se leen con caché (DECORATOR) y se comparte entre peticiones
        self._tiendas = TiendaDAOConCache(TiendaDAOSQLAlchemy(), ConfiguracionMetas().cache_tiendas_segundos)

    def crear_tienda_dao(self):
        return self._tiendas

    def crear_meta_dao(self):
        from app.metas.dao.sqlalchemy_dao import MetaDAOSQLAlchemy
        return MetaDAOSQLAlchemy()

    def crear_historial_dao(self):
        from app.metas.dao.sqlalchemy_dao import HistorialDAOSQLAlchemy
        return HistorialDAOSQLAlchemy()

    def crear_venta_dao(self):
        from app.metas.adaptadores import VentaDesdeCumplimientoAdapter
        return VentaDesdeCumplimientoAdapter()


class FabricaMemoria(FabricaDAO):
    """Familia en memoria, con tiendas y ventas de ejemplo: pruebas sin base de datos."""

    def __init__(self, tiendas=None, ventas=None):
        from app.metas.dao import memoria_dao as m
        self._tiendas = m.TiendaDAOMemoria(tiendas if tiendas is not None else m.tiendas_de_ejemplo())
        self._metas = m.MetaDAOMemoria(self._tiendas)
        self._historial = m.HistorialDAOMemoria()
        self._ventas = m.VentaDAOMemoria(ventas)

    def crear_tienda_dao(self):
        return self._tiendas

    def crear_meta_dao(self):
        return self._metas

    def crear_historial_dao(self):
        return self._historial

    def crear_venta_dao(self):
        return self._ventas


_FABRICAS = {"sqlalchemy": FabricaSQLAlchemy, "memoria": FabricaMemoria}


def fabrica_configurada():
    """La fábrica que dice METAS_ORIGEN_DATOS en el .env (por defecto, la base de datos)."""
    origen = ConfiguracionMetas().origen_datos
    if origen not in _FABRICAS:
        raise ValueError(f"METAS_ORIGEN_DATOS no válido: {origen!r} (use: {', '.join(_FABRICAS)})")
    return _FABRICAS[origen]()
