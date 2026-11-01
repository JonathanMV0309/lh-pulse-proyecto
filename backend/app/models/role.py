from app.extensions import db


class Role(db.Model):

    __tablename__ = "roles"

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

    users = db.relationship(
        "User",
        back_populates="role",
        lazy=True
    )