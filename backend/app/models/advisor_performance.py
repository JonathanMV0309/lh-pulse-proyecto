from datetime import datetime
from app.extensions import db

class AdvisorPerformance(db.Model):
    __tablename__ = "advisor_performance"

    id = db.Column(db.Integer, primary_key=True)
    advisor_id = db.Column(db.Integer, db.ForeignKey("advisors.id"), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    venta = db.Column(db.Numeric(15, 2), default=0)
    unidades = db.Column(db.Numeric(15, 2), default=0)
    facturas = db.Column(db.Numeric(15, 2), default=0)
    ticket_promedio = db.Column(db.Numeric(15, 2), default=0)
    upt = db.Column(db.Numeric(10, 4), default=0)

    # CAMPOS DE VERSIÓN / CORTE
    dia_corte = db.Column(db.Integer, nullable=True)
    es_cierre = db.Column(db.Boolean, default=False)
    activo = db.Column(db.Boolean, default=True)
    fecha_carga = db.Column(db.DateTime, default=datetime.utcnow)
    nombre_archivo = db.Column(db.String(255), nullable=True)

    advisor = db.relationship("Advisor", backref="performances")
    store = db.relationship("Store", backref="advisor_performances")

    __table_args__ = (
        db.Index("idx_advisor_perf_periodo_activo", "anio", "mes", "store_id", "advisor_id", "activo"),
    )

    def __repr__(self):
        return f"<AdvisorPerformance advisor={self.advisor_id} store={self.store_id} {self.anio}-{self.mes} corte={self.dia_corte} activo={self.activo}>"