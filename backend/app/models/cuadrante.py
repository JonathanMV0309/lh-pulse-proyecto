from datetime import datetime
from app.extensions import db


class CuadrantePersona(db.Model):
    """
    Persona que puede ser asignada al cuadrante de horarios.
    Incluye asesoras existentes y personal adicional (ej. la administradora).
    """
    __tablename__ = "cuadrante_personas"

    id = db.Column(db.Integer, primary_key=True)

    store_id = db.Column(
        db.Integer,
        db.ForeignKey("stores.id"),
        nullable=False
    )

    advisor_id = db.Column(
        db.Integer,
        db.ForeignKey("advisors.id"),
        nullable=True
    )

    nombre = db.Column(db.String(120), nullable=False)
    tipo = db.Column(db.String(30), default="ASESORA")  # ASESORA, ADMINISTRADORA, etc.

    activo = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store = db.relationship("Store", backref="cuadrante_personas")
    advisor = db.relationship("Advisor", backref="cuadrante_personas")

    def __repr__(self):
        return f"<CuadrantePersona {self.nombre} ({self.tipo})>"


class CuadranteAsignacion(db.Model):
    """
    Asignación de una persona a una fecha y turno concreto.
    """
    __tablename__ = "cuadrante_asignaciones"

    id = db.Column(db.Integer, primary_key=True)

    store_id = db.Column(
        db.Integer,
        db.ForeignKey("stores.id"),
        nullable=False
    )

    persona_id = db.Column(
        db.Integer,
        db.ForeignKey("cuadrante_personas.id"),
        nullable=False
    )

    fecha = db.Column(db.Date, nullable=False)
    turno = db.Column(db.String(30), nullable=False)  # APERTURA, CIERRE, etc.
    orden = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store = db.relationship("Store", backref="cuadrante_asignaciones")
    persona = db.relationship("CuadrantePersona", backref="asignaciones")

    def __repr__(self):
        return f"<CuadranteAsignacion {self.persona.nombre} {self.turno} {self.fecha}>"