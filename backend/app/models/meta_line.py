from app.extensions import db


class MetaLine(db.Model):

    __tablename__ = "meta_lines"

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
        db.Numeric(14, 2),
        default=0
    )

    meta_proporcional = db.Column(
        db.Numeric(14, 2),
        default=0
    )

    venta = db.Column(
        db.Numeric(14, 2),
        default=0
    )

    cumplimiento_pct = db.Column(
        db.Numeric(7, 4),
        default=0
    )

    store = db.relationship(
        "Store"
    )

    line = db.relationship(
        "Line"
    )