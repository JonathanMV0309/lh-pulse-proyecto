from app.extensions import db
from datetime import datetime


class UploadedFile(db.Model):

    __tablename__ = "uploaded_files"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # ==================================================
    # INFORMACIÓN DEL ARCHIVO
    # ==================================================

    nombre_archivo = db.Column(
        db.String(255),
        nullable=False
    )

    ruta_archivo = db.Column(
        db.String(500),
        nullable=False
    )

    # ==================================================
    # INFORMACIÓN DEL CORTE
    # ==================================================

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

    # ==================================================
    # INFORMACIÓN DE LA IMPORTACIÓN
    # ==================================================

    registros_importados = db.Column(
        db.Integer,
        default=0
    )

    estado = db.Column(
        db.String(20),
        default="ACTIVO",
        nullable=False
    )

    # ==================================================
    # USUARIO QUE SUBIÓ EL ARCHIVO
    # ==================================================

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    usuario = db.relationship(
        "User",
        backref="archivos_subidos"
    )

    # ==================================================
    # FECHAS
    # ==================================================

    fecha_subida = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    fecha_modificacion = db.Column(
        db.DateTime,
        nullable=True
    )

    def __repr__(self):
        return (
            f"<UploadedFile "
            f"{self.nombre_archivo} "
            f"{self.anio}-{self.mes}>"
        )