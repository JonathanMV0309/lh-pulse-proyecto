"""OBSERVER: cuando una meta se crea, se ajusta o se elimina, se avisa a quien le interese.

Problema: cada cambio de una meta debe quedar en el historial (HU-07) y en el registro de la
aplicación, y más adelante se quiere avisar a la tienda con una notificación. Si el servicio hiciera
todo eso directamente, cada aviso nuevo obligaría a modificarlo.

El servicio solo publica un EventoMeta; los observadores suscritos reaccionan cada uno a su manera.
Agregar un aviso nuevo = escribir un observador y suscribirlo. Complejidad: el orden y los errores
de los observadores no se ven en el servicio; por eso un observador que falla no tumba a los demás.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from app.metas.dto import MetaDTO

log = logging.getLogger("lhpulse.metas")


@dataclass
class EventoMeta:
    accion: str                       # creada | ajustada | eliminada
    meta: MetaDTO                     # la meta después del cambio (o la eliminada)
    valor_anterior: Optional[float]
    usuario: str


class ObservadorMeta:
    def notificar(self, evento):
        raise NotImplementedError


class PublicadorEventosMeta:

    def __init__(self):
        self._observadores = []

    def suscribir(self, observador):
        if observador not in self._observadores:
            self._observadores.append(observador)
        return self

    def retirar(self, observador):
        if observador in self._observadores:
            self._observadores.remove(observador)

    def publicar(self, evento):
        for o in list(self._observadores):
            try:
                o.notificar(evento)
            except Exception:                 # un aviso que falla no deshace el cambio ni frena a los demás
                log.exception("El observador %s falló con %s", type(o).__name__, evento.accion)


class HistorialObserver(ObservadorMeta):
    """Guarda cada cambio en metas_tienda_historial (HU-07), a través de su DAO."""

    def __init__(self, historial_dao):
        self.historial_dao = historial_dao

    def notificar(self, evento):
        m = evento.meta
        self.historial_dao.registrar(m.id, m.tienda_id, m.anio, m.mes, evento.accion, evento.valor_anterior,
                                     None if evento.accion == "eliminada" else m.valor, evento.usuario)


class RegistroLogObserver(ObservadorMeta):
    """Deja una línea en el registro de la aplicación (se ve con docker compose logs api)."""

    def notificar(self, evento):
        m = evento.meta
        log.info("Meta %s: %s %04d-%02d %s -> %s por %s", evento.accion, m.tienda_codigo or m.tienda_id, m.anio, m.mes,
                 evento.valor_anterior, None if evento.accion == "eliminada" else m.valor, evento.usuario)
