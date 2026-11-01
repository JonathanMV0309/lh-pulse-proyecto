from app.extensions import db


class Region(db.Model):
    __tablename__ = "regions"

    id = db.Column(db.Integer, primary_key=True)

    nombre = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    tiendas = db.relationship(
        "Store",
        back_populates="region"
    )
    