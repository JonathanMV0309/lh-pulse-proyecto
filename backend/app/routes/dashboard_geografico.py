from flask import Blueprint, render_template, session, abort, request

from app.models.user import User
from app.services.dashboard_geografico_service import (
    obtener_dashboard_geografico
)


dashboard_geografico_bp = Blueprint(
    "dashboard_geografico",
    __name__
)


ROLES_PERMITIDOS = {
    "ADMINISTRADOR",
    "TIENDA"
}


@dashboard_geografico_bp.route("/dashboard/geografico")
def dashboard_geografico():

    # ==========================================================
    # 1. VALIDAR SESIÓN
    # ==========================================================

    if "user_id" not in session:
        return "NO HAY SESION", 401


    usuario = User.query.get(session["user_id"])


    if not usuario:
        return "USUARIO NO EXISTE", 404


    # ==========================================================
    # 2. VALIDAR ROL
    # ==========================================================

    rol = (
        usuario.role.nombre.upper().strip()
        if usuario.role
        else ""
    )


    if rol not in ROLES_PERMITIDOS:
        abort(403)


    # ==========================================================
    # 3. LEER FILTROS
    # ==========================================================

    ciudad = request.args.get(
        "ciudad",
        default=None,
        type=str
    )

    clima = request.args.get(
        "clima",
        default=None,
        type=str
    )


    # ==========================================================
    # 4. OBTENER DATOS
    # ==========================================================

    datos = obtener_dashboard_geografico(
        ciudad=ciudad,
        clima=clima
    )


    # ==========================================================
    # 5. USUARIO
    # ==========================================================

    datos["usuario"] = usuario


    # ==========================================================
    # 6. RENDER
    # ==========================================================

    return render_template(
        "admin/dashboard_geografico.html",
        **datos
    )