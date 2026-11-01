"""Valores originales de la cuota de un corte antes de ajustarla por un cierre de tienda.

Tabla nueva e independiente: se crea sola la primera vez. Permite recalcular el ajuste las veces que
haga falta (siempre desde el valor original) y devolverlo si se borra la novedad de cierre.
"""
from datetime import datetime

from app.extensions import db


class AjusteCuota(db.Model):
    __tablename__ = "ajustes_cuota_cierre"

    compliance_id = db.Column(db.Integer, db.ForeignKey("compliance.id"), primary_key=True)
    cuota_total = db.Column(db.Float)
    cuota_proporcional = db.Column(db.Float)
    cumplimiento_pct = db.Column(db.Float)
    venta_promedio_dia = db.Column(db.Float)
    falta_para_cuota = db.Column(db.Float)
    dias_cerrada = db.Column(db.Integer, default=0)
    actualizado = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def crear_tabla_si_falta():
    AjusteCuota.__table__.create(bind=db.engine, checkfirst=True)
