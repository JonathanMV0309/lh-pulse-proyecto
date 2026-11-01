"""Presentaciones de Hilo que cada usuario ya vio (se muestran una sola vez).

Tabla nueva e independiente: se crea sola la primera vez que se usa.
"""
from datetime import datetime

from app.extensions import db


class PresentacionVista(db.Model):
    __tablename__ = "hilo_presentaciones_vistas"
    __table_args__ = (db.UniqueConstraint("user_id", "clave", name="uq_hilo_presentacion_usuario"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    clave = db.Column(db.String(60), nullable=False)
    visto = db.Column(db.DateTime, default=datetime.utcnow)


def crear_tabla_si_falta():
    PresentacionVista.__table__.create(bind=db.engine, checkfirst=True)
