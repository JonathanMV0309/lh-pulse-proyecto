from datetime import datetime

from app.extensions import db


class Compliance(db.Model):

    __tablename__ = "compliance"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # ==================================================
    # TIENDA
    # ==================================================

    store_id = db.Column(
        db.Integer,
        db.ForeignKey("stores.id"),
        nullable=False
    )

    # ==================================================
    # PERIODO
    # ==================================================

    anio = db.Column(
        db.Integer,
        nullable=False
    )

    mes = db.Column(
        db.Integer,
        nullable=False
    )

    # ==================================================
    # VENTAS
    # ==================================================

    venta_actual = db.Column(
        db.Numeric(15, 2),
        default=0
    )

    venta_anterior = db.Column(
        db.Numeric(15, 2),
        default=0
    )

    incremento = db.Column(
        db.Numeric(10, 4),
        default=0
    )

    # ==================================================
    # CUOTAS
    # ==================================================

    cuota_proporcional = db.Column(
        db.Numeric(15, 2),
        default=0
    )

    cuota_total = db.Column(
        db.Numeric(15, 2),
        default=0
    )

    cumplimiento_pct = db.Column(
        db.Numeric(10, 4),
        default=0
    )

    falta_para_cuota = db.Column(
        db.Numeric(15, 2),
        default=0
    )

    # ==================================================
    # INDICADORES DIARIOS
    # ==================================================

    venta_promedio_dia = db.Column(
        db.Numeric(15, 2),
        default=0
    )

    trafico = db.Column(
        db.Integer,
        default=0
    )

    facturas = db.Column(
        db.Integer,
        default=0
    )

    conversion = db.Column(
        db.Numeric(10, 4),
        default=0
    )

    ticket_promedio = db.Column(
        db.Numeric(15, 2),
        default=0
    )

    # ==================================================
    # NUEVO: DIF. ACUM (ACUM ENE-HASTA LA FECHA)
    # ==================================================

    dif_acum = db.Column(
        db.Numeric(15, 2),
        default=0,
        nullable=True
    )

    # ==================================================
    # CONTROL DE CORTE
    # ==================================================

    dia_corte = db.Column(
        db.Integer,
        nullable=True
    )

    es_cierre = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    activo = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    fecha_carga = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    nombre_archivo = db.Column(
        db.String(255),
        nullable=True
    )

    # ==================================================
    # RELACIONES
    # ==================================================

    store = db.relationship(
        "Store",
        backref="compliance_records"
    )

    # ==================================================
    # ÍNDICES
    # ==================================================

    __table_args__ = (

        db.Index(
            "idx_compliance_periodo_corte",
            "anio",
            "mes",
            "dia_corte",
            "store_id"
        ),

        db.Index(
            "idx_compliance_periodo_activo",
            "anio",
            "mes",
            "activo",
            "store_id"
        ),

    )

    # ==================================================
    # REPRESENTACIÓN
    # ==================================================

    def __repr__(self):

        return (
            f"<Compliance "
            f"store={self.store_id} "
            f"{self.anio}-{self.mes} "
            f"corte={self.dia_corte} "
            f"activo={self.activo}>"
        )