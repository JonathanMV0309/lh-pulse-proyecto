from datetime import datetime
from app.extensions import db


class TraficoCarga(db.Model):
    __tablename__ = 'trafico_cargas'
    id = db.Column(db.Integer, primary_key=True)
    sha256 = db.Column(db.String(64), nullable=True)
    nombre_archivo = db.Column(db.String(255), nullable=True)
    resumen = db.Column(db.JSON, nullable=True)
    actualizado = db.Column(db.DateTime, default=datetime.utcnow)


class TraficoHorario(db.Model):
    __tablename__ = 'trafico_horario'
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), primary_key=True)
    fecha = db.Column(db.Date, primary_key=True)
    hora = db.Column(db.Integer, primary_key=True)
    trafico = db.Column(db.Integer, nullable=True)
    facturas = db.Column(db.Integer, nullable=True)
    sensor_error = db.Column(db.Boolean, nullable=False, default=False)
    __table_args__ = (
        db.CheckConstraint('hora >= 0 AND hora <= 23', name='ck_trafico_hora'),
        db.CheckConstraint('trafico >= 0', name='ck_trafico_conteo'),
        db.CheckConstraint('facturas >= 0', name='ck_trafico_facturas'),
        db.Index('ix_trafico_fecha_hora', 'fecha', 'hora'),
    )
