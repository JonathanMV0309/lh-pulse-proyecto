from app.extensions import db
from datetime import datetime


class ArchivoImportado(db.Model):

    __tablename__ = "archivos_importados"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nombre_archivo = db.Column(
        db.String(255),
        nullable=False
    )

    ruta = db.Column(
        db.String(500),
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

    dia_corte = db.Column(
        db.Integer,
        nullable=False
    )

    es_cierre = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    fecha_carga = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    fecha_modificacion = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    estado = db.Column(
        db.String(20),
        default="ACTIVO",
        nullable=False
    )

    usuario = db.relationship(
        "User",
        backref="archivos_importados"
    )