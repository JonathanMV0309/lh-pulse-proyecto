"""Novedades del personal de las tiendas (las diligencia Talento Humano).

Tabla nueva e independiente: se crea sola la primera vez (no modifica las que ya existen).
"""
from datetime import datetime

from app.extensions import db


class NovedadPersonal(db.Model):
    __tablename__ = "novedades_personal"

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)
    advisor_id = db.Column(db.Integer, db.ForeignKey("advisors.id"), nullable=True)   # vacío: administradora o persona sin código
    nombre = db.Column(db.String(150), nullable=True)      # nombre de la persona (o «Administradora»)
    cargo = db.Column(db.String(30), nullable=True)
    tipo = db.Column(db.String(30), nullable=False)
    desde = db.Column(db.Date, nullable=False)
    hasta = db.Column(db.Date, nullable=False)
    horas = db.Column(db.Float, nullable=True)             # horas de ausencia (si aplica)
    tienda_destino_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=True)   # traslado
    observacion = db.Column(db.String(500), nullable=True)  # solo la ve Talento Humano
    creado_por = db.Column(db.String(120), nullable=True)
    creado = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def crear_tabla_si_falta():
    NovedadPersonal.__table__.create(bind=db.engine, checkfirst=True)
