from datetime import datetime

from app.extensions import db


class MetaTienda(db.Model):
    """Meta de venta mensual de una tienda (HU-06). Una sola por tienda y mes."""

    __tablename__ = "metas_tienda"
    __table_args__ = (
        db.UniqueConstraint("store_id", "anio", "mes", name="uq_meta_tienda_periodo"),
    )

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    valor = db.Column(db.Numeric(15, 2), nullable=False)
    nota = db.Column(db.String(255))
    actualizado_por = db.Column(db.String(120))
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    store = db.relationship("Store")


class MetaTiendaHistorial(db.Model):
    """Cada cambio de una meta: quién, cuándo, valor anterior y nuevo (HU-07)."""

    __tablename__ = "metas_tienda_historial"

    id = db.Column(db.Integer, primary_key=True)
    # Sin llave foránea: el historial se conserva aunque la meta se elimine
    meta_id = db.Column(db.Integer, nullable=False, index=True)
    store_id = db.Column(db.Integer, nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    accion = db.Column(db.String(20), nullable=False)
    valor_anterior = db.Column(db.Numeric(15, 2))
    valor_nuevo = db.Column(db.Numeric(15, 2))
    usuario = db.Column(db.String(120))
    fecha = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
