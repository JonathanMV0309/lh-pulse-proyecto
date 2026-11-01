from app.extensions import db


class Store(db.Model):

    __tablename__ = "stores"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    codigo = db.Column(
        db.String(10),
        unique=True,
        nullable=False
    )

    nombre = db.Column(
        db.String(120),
        nullable=False
    )

    # ==================================================
    # UBICACIÓN
    # ==================================================

    ciudad = db.Column(
        db.String(80),
        nullable=True
    )

    clima = db.Column(
        db.String(30),
        nullable=True
    )

    # Nuevas columnas para coordenadas geográficas
    lat = db.Column(
        db.Float,
        nullable=True
    )

    lng = db.Column(
        db.Float,
        nullable=True
    )

    # ==================================================
    # RELACIONES ORGANIZACIONALES
    # ==================================================

    region_id = db.Column(
        db.Integer,
        db.ForeignKey("regions.id")
    )

    supervisor_id = db.Column(
        db.Integer,
        db.ForeignKey("supervisors.id")
    )

    estado = db.Column(
        db.String(20),
        default="ACTIVA"
    )

    # ==================================================
    # RELACIONES
    # ==================================================

    region = db.relationship(
        "Region",
        back_populates="tiendas"
    )

    supervisor = db.relationship(
        "Supervisor",
        back_populates="tiendas"
    )

    asesoras = db.relationship(
        "Advisor",
        back_populates="store"
    )