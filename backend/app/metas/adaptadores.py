"""ADAPTER: la tabla heredada «compliance» vista como un VentaDAO.

Problema: la venta de cada tienda ya existe, pero en la tabla compliance que llena el importador de
Excel del Sprint 1. Esa tabla tiene otra forma: varias filas por mes (una por cada informe, con su día
de corte), una marca «activo», valores Numeric y el código de tienda en store_id. El módulo de metas
solo necesita «cuánto ha vendido cada tienda este mes y hasta qué día».

El adaptador cumple el contrato VentaDAO (dao/base.py) traduciendo esa tabla, sin tocar el
importador ni su tabla. Complejidad: una clase más, y si compliance cambia, hay que ajustar aquí.
"""
from sqlalchemy import func

from app.extensions import db
from app.metas.dao.base import VentaDAO
from app.metas.dto import VentaMesDTO
from app.models.compliance import Compliance


class VentaDesdeCumplimientoAdapter(VentaDAO):

    def ventas_del_mes(self, anio, mes):
        # El informe más reciente de cada tienda en ese mes (el de mayor día de corte, entre los activos)
        ultimo = (db.session.query(Compliance.store_id, func.max(Compliance.dia_corte).label("corte"))
                  .filter(Compliance.anio == anio, Compliance.mes == mes, Compliance.activo.is_(True))
                  .group_by(Compliance.store_id).subquery())
        filas = (db.session.query(Compliance.store_id, Compliance.venta_actual, Compliance.dia_corte)
                 .join(ultimo, (Compliance.store_id == ultimo.c.store_id) & (Compliance.dia_corte == ultimo.c.corte))
                 .filter(Compliance.anio == anio, Compliance.mes == mes, Compliance.activo.is_(True))
                 .all())
        return {store_id: VentaMesDTO(valor=float(venta or 0), dia_corte=int(corte or 0)) for store_id, venta, corte in filas}
