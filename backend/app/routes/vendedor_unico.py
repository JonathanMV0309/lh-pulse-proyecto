from flask import Blueprint, render_template, request, session, abort

from app.extensions import db
from app.models.user import User
from app.models.store import Store
from app.models import Advisor, AdvisorPerformance


vendedor_unico_bp = Blueprint(
    "vendedor_unico",
    __name__,
    url_prefix="/vendedor-unico"
)


ROLES_ADMIN = {"ADMIN", "ADMINISTRADOR"}


def obtener_usuario_actual():
    if "user_id" not in session:
        return None

    return User.query.get(session["user_id"])


def verificar_acceso():
    usuario = obtener_usuario_actual()

    if not usuario:
        abort(401)

    if not usuario.role:
        abort(403)

    rol = usuario.role.nombre.upper().strip()

    if rol not in ROLES_ADMIN:
        abort(403)

    return usuario


@vendedor_unico_bp.route("/", methods=["GET"])
def pagina_vendedor_unico():

    usuario = verificar_acceso()

    tiendas = (
        Store.query
        .filter_by(estado="ACTIVA")
        .order_by(Store.codigo)
        .all()
    )

    store_id = request.args.get(
        "store_id",
        type=int
    )

    anio = request.args.get(
        "anio",
        type=int,
        default=2026
    )

    mes = request.args.get(
        "mes",
        type=int,
        default=7
    )

    vendedores = []

    if store_id:

        vendedores = (
            db.session.query(
                Advisor.id.label("advisor_id"),
                Advisor.nombre.label("nombre"),
                AdvisorPerformance.venta.label("venta"),
                AdvisorPerformance.activo.label("activo")
            )
            .join(
                AdvisorPerformance,
                Advisor.id == AdvisorPerformance.advisor_id
            )
            .filter(
                AdvisorPerformance.store_id == store_id,
                AdvisorPerformance.anio == anio,
                AdvisorPerformance.mes == mes
            )
            .filter(
                Advisor.nombre.ilike("%VENDEDOR UNICO%")
            )
            .order_by(
                Advisor.nombre.asc()
            )
            .all()
        )

    return render_template(
        "vendedor_unico.html",
        usuario=usuario,
        tiendas=tiendas,
        vendedores=vendedores,
        store_id_actual=store_id,
        anio_actual=anio,
        mes_actual=mes
    )