from app.extensions import db


class Goal(db.Model):

    __tablename__ = "goals"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nombre = db.Column(
        db.String(100),
        nullable=False
    )

    descripcion = db.Column(
        db.String(255)
    )

    peso = db.Column(
        db.Float,
        default=1
    )

    meta = db.Column(
        db.Float,
        nullable=False
    )

    activo = db.Column(
        db.Boolean,
        default=True
    )

    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id"),
        nullable=False
    )

    category = db.relationship(
        "Category",
        back_populates="goals"
    )