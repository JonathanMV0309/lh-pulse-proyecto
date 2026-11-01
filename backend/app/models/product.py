from app.extensions import db


class Product(db.Model):

    __tablename__ = "products"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nombre = db.Column(
        db.String(150),
        nullable=False
    )

    codigo = db.Column(
        db.String(50),
        unique=True,
        nullable=True
    )

    estado = db.Column(
        db.String(20),
        default="ACTIVO"
    )

    # =====================================================
    # LÍNEA
    # =====================================================

    line_id = db.Column(
        db.Integer,
        db.ForeignKey("lines.id"),
        nullable=True
    )

    line = db.relationship(
        "Line",
        back_populates="productos"
    )