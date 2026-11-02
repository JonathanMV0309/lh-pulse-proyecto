"""BUILDER: arma, paso a paso, el resumen de una tienda en un mes (TiendaMetaDTO).

Problema: cada fila de la consulta (HU-05) junta datos de tres fuentes (tienda, meta y venta) y
cálculos que dependen de lo que exista: sin meta no hay cumplimiento, sin informe de ventas no hay día
de corte, y el semáforo depende de la estrategia elegida. Un constructor con 14 parámetros en el
orden correcto sería frágil y repetiría esa lógica en cada lugar que arma un resumen.

El builder recibe las partes en cualquier orden y en construir() calcula lo que falta y valida que
estén las obligatorias. Complejidad: una clase más que mantener junto al DTO.
"""
from app.metas.dto import TiendaMetaDTO


class ResumenTiendaBuilder:

    def __init__(self):
        self._tienda = self._anio = self._mes = self._meta = self._venta = self._estrategia = None

    def para_tienda(self, tienda):
        self._tienda = tienda
        return self

    def en_periodo(self, anio, mes):
        self._anio, self._mes = anio, mes
        return self

    def con_meta(self, meta):
        self._meta = meta               # MetaDTO o None
        return self

    def con_venta(self, venta):
        self._venta = venta             # VentaMesDTO o None
        return self

    def calificado_con(self, estrategia):
        self._estrategia = estrategia   # EstrategiaSemaforo (STRATEGY)
        return self

    def construir(self):
        if self._tienda is None or self._anio is None or self._estrategia is None:
            raise ValueError("Faltan la tienda, el periodo o la estrategia del semáforo")
        venta = self._venta.valor if self._venta else 0.0
        dia_corte = self._venta.dia_corte if self._venta else None
        if self._meta is None:
            meta_al_corte = pct = None
            semaforo, estado = "gris", "sin_meta"
        else:
            evaluacion = self._estrategia.evaluar(self._meta.valor, venta, dia_corte, self._anio, self._mes)
            meta_al_corte, pct, semaforo = evaluacion.meta_al_corte, evaluacion.cumplimiento_pct, evaluacion.semaforo
            estado = "sin_ventas" if self._venta is None else "con_meta"
        return TiendaMetaDTO(
            tienda_id=self._tienda.id, tienda_codigo=self._tienda.codigo, tienda_nombre=self._tienda.nombre,
            ciudad=self._tienda.ciudad, anio=self._anio, mes=self._mes,
            meta_id=self._meta.id if self._meta else None, meta=self._meta.valor if self._meta else None,
            venta=venta, dia_corte=dia_corte, meta_al_corte=meta_al_corte, cumplimiento_pct=pct,
            semaforo=semaforo, estado=estado,
        )
