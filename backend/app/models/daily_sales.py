from datetime import datetime
from app.extensions import db


class DailySales(db.Model):
    __tablename__ = "daily_sales"

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=True)
    anio = db.Column(db.Integer, nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    dia = db.Column(db.Integer, nullable=False)

    venta_2025 = db.Column(db.Numeric(15, 2), default=0)
    venta_2026 = db.Column(db.Numeric(15, 2), default=0)
    diferencia = db.Column(db.Numeric(15, 2), default=0)          # NUEVO
    incremento_pct = db.Column(db.Numeric(15, 4), default=0)      # CAMBIADO

    dia_semana_2025 = db.Column(db.String(20), nullable=True)
    dia_semana_2026 = db.Column(db.String(20), nullable=True)

    dia_corte = db.Column(db.Integer, nullable=True)
    es_cierre = db.Column(db.Boolean, default=False)
    activo = db.Column(db.Boolean, default=True)
    fecha_carga = db.Column(db.DateTime, default=datetime.utcnow)
    nombre_archivo = db.Column(db.String(255), nullable=True)

    store = db.relationship("Store", backref="daily_sales")

    __table_args__ = (
        db.Index("idx_daily_sales_periodo_activo", "anio", "mes", "activo"),
        db.Index("idx_daily_sales_periodo_dia", "anio", "mes", "dia"),
    )