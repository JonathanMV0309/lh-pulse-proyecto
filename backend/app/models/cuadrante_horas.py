"""Planilla de horas del equipo (formato GTH-ODSCTD-003 de Talento Humano).

Tablas nuevas e independientes de las del cuadrante: se crean solas la primera vez
(no modifican las tablas que ya existen).
"""
from datetime import datetime

from app.extensions import db


class CuadranteHoras(db.Model):
    """Entrada, salida y novedad de una persona en un día."""
    __tablename__ = "cuadrante_horas"
    __table_args__ = (db.UniqueConstraint("persona_id", "fecha", name="uq_cuadrante_horas_persona_fecha"),)

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)
    persona_id = db.Column(db.Integer, db.ForeignKey("cuadrante_personas.id"), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    entrada = db.Column(db.String(5), nullable=True)    # "HH:MM"
    salida = db.Column(db.String(5), nullable=True)
    novedad = db.Column(db.String(20), nullable=False, default="TRABAJA")
    observacion = db.Column(db.String(200), nullable=True)
    actualizado = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CuadranteSemanaObs(db.Model):
    """Observaciones de la semana de una persona (columna «Observaciones» del formato)."""
    __tablename__ = "cuadrante_semana_obs"
    __table_args__ = (db.UniqueConstraint("persona_id", "semana", name="uq_cuadrante_semana_obs"),)

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)
    persona_id = db.Column(db.Integer, db.ForeignKey("cuadrante_personas.id"), nullable=False)
    semana = db.Column(db.Date, nullable=False)   # domingo con el que empieza la semana
    texto = db.Column(db.String(300), nullable=True)


class CuadrantePersonaDato(db.Model):
    """Cargo y cédula de cada persona para la planilla (Administradora, Subadministradora, Segunda, Asesora, Auxiliar…)."""
    __tablename__ = "cuadrante_persona_datos"

    persona_id = db.Column(db.Integer, db.ForeignKey("cuadrante_personas.id"), primary_key=True)
    cargo = db.Column(db.String(30), nullable=True)
    cedula = db.Column(db.String(20), nullable=True)


class HorarioTienda(db.Model):
    """Horario de apertura y cierre por tipo de día (L-J, V-S, D-F…)."""
    __tablename__ = "horario_tienda"

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)
    dias = db.Column(db.String(10), nullable=False)
    apertura = db.Column(db.String(5), nullable=False)
    cierre = db.Column(db.String(5), nullable=False)
    orden = db.Column(db.Integer, default=0)


class CuadranteSinAlmuerzo(db.Model):
    """Días en que la persona NO almorzó: se le cuentan todas las horas (por defecto se descuenta 1 h)."""
    __tablename__ = "cuadrante_sin_almuerzo"
    __table_args__ = (db.UniqueConstraint("persona_id", "fecha", name="uq_cuadrante_sin_almuerzo"),)

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)
    persona_id = db.Column(db.Integer, db.ForeignKey("cuadrante_personas.id"), nullable=False)
    fecha = db.Column(db.Date, nullable=False)


TABLAS = [CuadranteHoras, CuadranteSemanaObs, CuadrantePersonaDato, HorarioTienda, CuadranteSinAlmuerzo]


def crear_tablas_si_faltan():
    """Crea solo las tablas de la planilla que no existan (no toca las demás)."""
    for modelo in TABLAS:
        modelo.__table__.create(bind=db.engine, checkfirst=True)
