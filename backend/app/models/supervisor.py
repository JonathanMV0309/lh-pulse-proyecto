from app.extensions import db


class Supervisor(db.Model):
    __tablename__ = "supervisors"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nombre = db.Column(
        db.String(80),
        nullable=False,
        unique=True
    )

    estado = db.Column(
        db.String(20),
        default="ACTIVO"
    )


    tiendas = db.relationship(
        "Store",
        back_populates="supervisor"
    )