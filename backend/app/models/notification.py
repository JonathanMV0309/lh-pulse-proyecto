from datetime import datetime

from app.extensions import db


class Notification(db.Model):

    __tablename__ = "notifications"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    titulo = db.Column(
        db.String(120),
        nullable=False
    )

    mensaje = db.Column(
        db.Text,
        nullable=False
    )

    # Si store_id es NULL => notificación global
    store_id = db.Column(
        db.Integer,
        db.ForeignKey("stores.id"),
        nullable=True
    )

    creador_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    fecha_creacion = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    store = db.relationship(
        "Store",
        backref="notificaciones"
    )

    creador = db.relationship(
        "User",
        backref="notificaciones_creadas"
    )

    def __repr__(self):
        alcance = "GLOBAL" if self.store_id is None else f"TIENDA {self.store_id}"
        return f"<Notification {self.id} [{alcance}] {self.titulo}>"