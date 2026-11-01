"""STRATEGY: cómo se califica si una tienda va bien con su meta (semáforo verde, amarillo o rojo).

Problema: hay dos formas válidas de medirlo y la administración puede preferir una u otra:
- Proporcional: a mitad de mes se compara con la mitad de la meta (la meta «al día de corte»).
  Es la que usa Pulse en el día a día: una tienda no está mal el día 10 por no tener la meta completa.
- Mensual: se compara con la meta completa del mes (útil al cierre).
Con if/else en el servicio, cada forma nueva obligaría a tocar el servicio y sus pruebas.

Cada forma es una clase con el mismo método evaluar(); el servicio recibe la que dice el .env
(METAS_SEMAFORO). Complejidad: más clases, y hay que explicar a la administración cuál está activa.
"""
import calendar
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.metas.configuracion import ConfiguracionMetas


@dataclass
class Evaluacion:
    meta_al_corte: float
    cumplimiento_pct: float
    semaforo: str


class EstrategiaSemaforo(ABC):
    nombre = ""
    descripcion = ""

    def __init__(self, umbral_verde=1.0, umbral_amarillo=0.9):
        self.umbral_verde, self.umbral_amarillo = umbral_verde, umbral_amarillo

    @abstractmethod
    def meta_comparable(self, meta, dia_corte, anio, mes):
        """Contra qué parte de la meta se compara la venta."""

    def evaluar(self, meta, venta, dia_corte, anio, mes):
        base = self.meta_comparable(meta, dia_corte, anio, mes)
        pct = round(venta / base * 100, 1) if base > 0 else 0.0
        if pct >= self.umbral_verde * 100:
            color = "verde"
        elif pct >= self.umbral_amarillo * 100:
            color = "amarillo"
        else:
            color = "rojo"
        return Evaluacion(meta_al_corte=round(base, 2), cumplimiento_pct=pct, semaforo=color)


class SemaforoProporcional(EstrategiaSemaforo):
    nombre = "proporcional"
    descripcion = "Venta contra la meta proporcional al día de corte"

    def meta_comparable(self, meta, dia_corte, anio, mes):
        dias = calendar.monthrange(anio, mes)[1]
        if not dia_corte:
            return meta
        return meta * min(dia_corte, dias) / dias


class SemaforoMensual(EstrategiaSemaforo):
    nombre = "mensual"
    descripcion = "Venta contra la meta completa del mes"

    def meta_comparable(self, meta, dia_corte, anio, mes):
        return meta


ESTRATEGIAS = {e.nombre: e for e in (SemaforoProporcional, SemaforoMensual)}


def estrategia_configurada():
    c = ConfiguracionMetas()
    clase = ESTRATEGIAS.get(c.semaforo, SemaforoProporcional)
    return clase(c.umbral_verde, c.umbral_amarillo)
