from datetime import datetime
from app.extensions import db


class ChecklistVisita(db.Model):
    """
    Guarda la información cualitativa del checklist de visita a tienda.
    Los datos numéricos (ventas, tráfico, ticket, ranking) no se guardan
    porque se calculan en tiempo real desde Compliance/AdvisorPerformance.
    """
    __tablename__ = "checklist_visitas"

    id = db.Column(db.Integer, primary_key=True)

    store_id = db.Column(
        db.Integer,
        db.ForeignKey("stores.id"),
        nullable=False
    )

    fecha_visita = db.Column(db.Date, nullable=False)
    supervisor_email = db.Column(db.String(120), nullable=False)

    # Respuestas del checklist cualitativo:
    # {"Exhibición y visual merchandising": {"Vitrina principal...": "si", "obs": "..."}, ...}
    respuestas = db.Column(db.JSON, nullable=True)

    cumplimiento_pct = db.Column(db.Float, default=0.0)
    items_no = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store = db.relationship("Store", backref="checklist_visitas")

    def __repr__(self):
        return f"<ChecklistVisita store={self.store_id} fecha={self.fecha_visita}>"