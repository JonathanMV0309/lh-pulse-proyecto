from app.extensions import db


class Sale(db.Model):

    __tablename__ = "sales"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    fecha = db.Column(
        db.Date,
        nullable=False
    )

    store_id = db.Column(
        db.Integer,
        db.ForeignKey("stores.id"),
        nullable=False
    )

    advisor_id = db.Column(
        db.Integer,
        db.ForeignKey("advisors.id"),
        nullable=True
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=True
    )

    cantidad = db.Column(
        db.Integer,
        default=1
    )

    venta = db.Column(
        db.Float,
        nullable=False
    )

    store = db.relationship(
        "Store"
    )

    advisor = db.relationship(
        "Advisor",
        back_populates="ventas"
    )

    product = db.relationship(
        "Product"
    )