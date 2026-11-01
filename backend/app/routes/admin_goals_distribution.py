from flask import Blueprint, render_template, request, session
from functools import wraps

from app.models.user import User
from app.models.store import Store
from app.services.advisor_goal_service import (
    obtener_meta_tienda,
    calcular_metas_asesoras
)


admin_goals_distribution_bp = Blueprint(
    "admin_goals_distribution",
    __name__,
    url_prefix="/admin"
)


ROLES_ADMIN = {
    "ADMIN",
    "ADMINISTRADOR"
}


def admin_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:
            return "No autenticado", 401

        usuario = User.query.get(
            session["user_id"]
        )

        if (
            not usuario
            or usuario.role.nombre.upper().strip()
            not in ROLES_ADMIN
        ):
            return "Acceso denegado", 403

        return f(*args, **kwargs)

    return decorated_function


# ==========================================================
# DISTRIBUCIÓN DE METAS
# ==========================================================

@admin_goals_distribution_bp.route(
    "/metas/distribucion",
    methods=["GET"]
)
@admin_required
def distribucion_metas():

    # ------------------------------------------------------
    # Tiendas activas
    # ------------------------------------------------------

    tiendas = (
        Store.query
        .filter_by(
            estado="ACTIVA"
        )
        .order_by(
            Store.codigo
        )
        .all()
    )

    # ------------------------------------------------------
    # Parámetros
    # ------------------------------------------------------

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

    # ------------------------------------------------------
    # Valores iniciales
    # ------------------------------------------------------

    meta_tienda = 0

    distribucion = None

    # ------------------------------------------------------
    # Si hay tienda seleccionada
    # ------------------------------------------------------

    if store_id:

        # Meta de la tienda
        meta_tienda = obtener_meta_tienda(
            store_id,
            anio,
            mes
        )

        # Distribución automática
        distribucion = calcular_metas_asesoras(
            store_id,
            anio,
            mes,
            meta_tienda
        )

    return render_template(
        "admin_goals_distribution.html",

        tiendas=tiendas,

        store_id_actual=store_id,

        anio_actual=anio,

        mes_actual=mes,

        meta_tienda=meta_tienda,

        distribucion=distribucion
    )