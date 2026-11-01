from datetime import datetime

from app.extensions import db


class NotificationRead(db.Model):

    __tablename__ = "notification_reads"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    notification_id = db.Column(
        db.Integer,
        db.ForeignKey("notifications.id"),
        nullable=False
    )

    store_id = db.Column(
        db.Integer,
        db.ForeignKey("stores.id"),
        nullable=False
    )

    fecha_lectura = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    notification = db.relationship(
        "Notification",
        backref="lecturas"
    )

    store = db.relationship(
        "Store",
        backref="lecturas_notificaciones"
    )

    __table_args__ = (
        db.UniqueConstraint(
            "notification_id",
            "store_id",
            name="uq_notification_read"
        ),
    )