from datetime import datetime

from app.extensions import db


class MensajeHilo(db.Model):
    """
    Mensaje que un administrador deja para que Hilo lo diga
    cuando los usuarios entren a la página.
    """

    __tablename__ = "mensajes_hilo"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    texto = db.Column(
        db.String(400),
        nullable=False
    )

    # celebra | anima | aviso  (cómo lo dice Hilo)
    tono = db.Column(
        db.String(20),
        nullable=False,
        default="anima"
    )

    # todas | seleccion | todos (tiendas + administradores y supervisores)
    destino = db.Column(
        db.String(20),
        nullable=False,
        default="todas"
    )

    # Ids de tiendas separados por coma cuando destino = seleccion
    tiendas = db.Column(
        db.Text,
        nullable=True
    )

    desde = db.Column(
        db.Date,
        nullable=False
    )

    hasta = db.Column(
        db.Date,
        nullable=False
    )

    activo = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    creado_por = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    creado = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.now
    )

    autor = db.relationship(
        "User",
        lazy="joined"
    )

    def ids_tiendas(self):
        return {int(x) for x in (self.tiendas or "").split(",") if x.strip().isdigit()}


class MensajeHiloVisto(db.Model):
    """Quién ya vio cada mensaje (Hilo no lo repite)."""

    __tablename__ = "mensajes_hilo_vistos"

    __table_args__ = (
        db.UniqueConstraint("mensaje_id", "user_id", name="uq_mensaje_hilo_visto"),
    )

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    mensaje_id = db.Column(
        db.Integer,
        db.ForeignKey("mensajes_hilo.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    visto = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.now
    )
