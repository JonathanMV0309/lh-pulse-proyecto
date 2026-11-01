from app.extensions import db


class Advisor(db.Model):

    __tablename__ = "advisors"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nombre = db.Column(
        db.String(150),
        nullable=False
    )

    store_id = db.Column(
        db.Integer,
        db.ForeignKey("stores.id"),
        nullable=True
    )

    es_generico = db.Column(
        db.Boolean,
        default=False
    )

    estado = db.Column(
        db.String(20),
        default="ACTIVO"
    )

    store = db.relationship(
        "Store",
        back_populates="asesoras"
    )

    ventas = db.relationship(
        "Sale",
        back_populates="advisor"
    )