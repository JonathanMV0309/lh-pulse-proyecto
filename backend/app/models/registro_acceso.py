from datetime import datetime

from app.extensions import db


class RegistroAcceso(db.Model):
    """
    Bitácora de inicios de sesión: quién entró, cuándo, desde dónde
    y los intentos fallidos. Solo se agregan filas; nunca se editan.
    """

    __tablename__ = "registro_accesos"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    fecha = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.now,
        index=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Lo que escribieron en el campo usuario (sirve cuando el usuario no existe)
    correo = db.Column(
        db.String(150),
        nullable=True
    )

    # ok | clave_incorrecta | usuario_no_existe | salida
    resultado = db.Column(
        db.String(30),
        nullable=False,
        index=True
    )

    ip = db.Column(
        db.String(45),
        nullable=True
    )

    navegador = db.Column(
        db.String(300),
        nullable=True
    )

    usuario = db.relationship(
        "User",
        lazy="joined"
    )
