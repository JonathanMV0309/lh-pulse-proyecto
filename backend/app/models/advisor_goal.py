from datetime import datetime
from app.extensions import db

class AdvisorGoal(db.Model):
    __tablename__ = "advisor_goals"

    id = db.Column(db.Integer, primary_key=True)
    advisor_id = db.Column(db.Integer, db.ForeignKey("advisors.id"), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    meta_venta = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    # La clasificación es por período porque una asesora puede ser fija un mes
    # y auxiliar al siguiente.
    tipo_asesora = db.Column(db.String(20), nullable=False, default="FIJA")
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    advisor = db.relationship("Advisor", backref="goals")
    store = db.relationship("Store", backref="advisor_goals")

    # Restricción única
    __table_args__ = (
        db.UniqueConstraint(
            "advisor_id", "store_id", "anio", "mes",
            name="uq_advisor_goal_period"
        ),
        db.Index("idx_advisor_goals_period", "anio", "mes"),
        db.Index("idx_advisor_goals_advisor", "advisor_id"),
        db.Index("idx_advisor_goals_store", "store_id"),
        db.CheckConstraint(
            "tipo_asesora IN ('FIJA', 'AUXILIAR')",
            name="ck_advisor_goals_tipo_asesora"
        ),
    )

    def __repr__(self):
        return f"<AdvisorGoal advisor={self.advisor_id} store={self.store_id} {self.anio}-{self.mes} {self.meta_venta}>"
