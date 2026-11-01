from app.extensions import db


class Line(db.Model):

    __tablename__ = "lines"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nombre = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    productos = db.relationship(
        "Product",
        back_populates="line"
    )