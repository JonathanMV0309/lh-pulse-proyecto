from app.extensions import db


class User(db.Model):

    __tablename__ = "users"


    id = db.Column(
        db.Integer,
        primary_key=True
    )


    nombre = db.Column(
        db.String(100),
        nullable=False
    )


    correo = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )


    password = db.Column(
        db.String(255),
        nullable=False
    )


    activo = db.Column(
        db.Boolean,
        default=True
    )


    # ==========================
    # ROL DEL USUARIO
    # ==========================

    role_id = db.Column(
        db.Integer,
        db.ForeignKey("roles.id"),
        nullable=False
    )


    # ==========================
    # RELACIONES OPERATIVAS
    # ==========================

    # Usuario tipo SUPERVISORA
    supervisor_id = db.Column(
        db.Integer,
        db.ForeignKey("supervisors.id"),
        nullable=True
    )


    # Usuario tipo TIENDA
    store_id = db.Column(
        db.Integer,
        db.ForeignKey("stores.id"),
        nullable=True
    )


    # Usuario tipo ASESORA
    advisor_id = db.Column(
        db.Integer,
        db.ForeignKey("advisors.id"),
        nullable=True
    )


    # ==========================
    # RELACIONES
    # ==========================

    role = db.relationship(
        "Role",
        back_populates="users"
    )


    supervisor = db.relationship(
        "Supervisor"
    )


    store = db.relationship(
        "Store"
    )


    advisor = db.relationship(
        "Advisor"
    )