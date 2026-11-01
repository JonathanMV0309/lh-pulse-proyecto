from app.extensions import db


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)

    nombre = db.Column(db.String(100), unique=True, nullable=False)

    descripcion = db.Column(db.String(255))

    activa = db.Column(db.Boolean, default=True)

    goals = db.relationship(
        "Goal",
        back_populates="category",
        lazy=True
    )