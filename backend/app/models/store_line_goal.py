from app.extensions import db


class StoreLineGoal(db.Model):

    __tablename__ = "store_line_goals"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    store_id = db.Column(
        db.Integer,
        db.ForeignKey("stores.id"),
        nullable=False
    )

    line_id = db.Column(
        db.Integer,
        db.ForeignKey("lines.id"),
        nullable=False
    )

    anio = db.Column(
        db.Integer,
        nullable=False
    )

    mes = db.Column(
        db.Integer,
        nullable=False
    )

    meta = db.Column(
        db.Float,
        default=0
    )

    meta_proporcional = db.Column(
        db.Float,
        default=0
    )

    venta = db.Column(
        db.Float,
        default=0
    )

    cumplimiento = db.Column(
        db.Float,
        default=0
    )

    store = db.relationship(
        "Store"
    )

    line = db.relationship(
        "Line"
    )