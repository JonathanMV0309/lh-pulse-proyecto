from datetime import datetime

from app.extensions import db


class DailyStoreSales(db.Model):
    """Ventas y unidades diarias por tienda, conservadas por corte."""

    __tablename__ = "daily_store_sales"

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(
        db.Integer,
        db.ForeignKey("stores.id"),
        nullable=False,
    )
    anio = db.Column(db.Integer, nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    dia = db.Column(db.Integer, nullable=False)
    venta = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    unidades = db.Column(db.Integer, nullable=False, default=0)
    dia_corte = db.Column(db.Integer, nullable=False)
    es_cierre = db.Column(db.Boolean, nullable=False, default=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    fecha_carga = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    nombre_archivo = db.Column(db.String(255), nullable=True)

    store = db.relationship("Store", backref="daily_store_sales")

    __table_args__ = (
        db.UniqueConstraint(
            "store_id",
            "anio",
            "mes",
            "dia",
            "dia_corte",
            name="uq_daily_store_sales_store_periodo_dia_corte",
        ),
        db.Index(
            "idx_daily_store_sales_periodo_corte",
            "anio",
            "mes",
            "dia_corte",
        ),
        db.Index(
            "idx_daily_store_sales_store_periodo",
            "store_id",
            "anio",
            "mes",
        ),
    )
