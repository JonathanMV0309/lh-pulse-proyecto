from datetime import datetime
from app.extensions import db

class ConversionDiaria(db.Model):
    __tablename__ = "conversion_diaria"

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    dia = db.Column(db.Integer, nullable=False)
    trafico = db.Column(db.Integer, default=0)
    facturas = db.Column(db.Integer, default=0)
    conversion = db.Column(db.Numeric(10, 4), default=0)

    # CAMPOS DE VERSIÓN / CORTE
    dia_corte = db.Column(db.Integer, nullable=True)
    es_cierre = db.Column(db.Boolean, default=False)
    activo = db.Column(db.Boolean, default=True)
    fecha_carga = db.Column(db.DateTime, default=datetime.utcnow)
    nombre_archivo = db.Column(db.String(255), nullable=True)

    store = db.relationship("Store", backref="conversion_diaria_records")

    __table_args__ = (
        db.Index("idx_conversion_periodo_activo", "anio", "mes", "store_id", "activo"),
    )

    def __repr__(self):
        return f"<ConversionDiaria store={self.store_id} {self.anio}-{self.mes}-{self.dia} corte={self.dia_corte} activo={self.activo}>"