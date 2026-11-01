from flask import (
    Blueprint,
    render_template,
    session,
    redirect,
    request,
    flash
)

from werkzeug.security import generate_password_hash

from app.extensions import db

from app.models.user import User
from app.models.store import Store
from app.models.supervisor import Supervisor
from app.models.advisor import Advisor
from app.models.role import Role


admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin"
)


# ==========================================================
# VERIFICAR ADMINISTRADOR
# ==========================================================

def administrador_requerido():

    if "user_id" not in session:
        return False

    usuario = User.query.get(session["user_id"])

    if usuario is None:
        return False

    if usuario.role is None:
        return False

    return usuario.role.nombre in [
        "Administrador",
        "ADMIN"
    ]


# ==========================================================
# PANEL PRINCIPAL
# ==========================================================

@admin_bp.route("/")
def panel():

    if not administrador_requerido():
        return redirect("/")

    usuarios = User.query.count()
    tiendas = Store.query.count()
    supervisores = Supervisor.query.count()
    asesoras = Advisor.query.count()

    lista_usuarios = (
        User.query
        .order_by(User.nombre.asc())
        .all()
    )

    return render_template(
        "admin/panel.html",
        usuarios=usuarios,
        tiendas=tiendas,
        supervisores=supervisores,
        asesoras=asesoras,
        lista_usuarios=lista_usuarios
    )


# ==========================================================
# USUARIOS
# ==========================================================

@admin_bp.route("/usuarios")
def usuarios():

    if not administrador_requerido():
        return redirect("/")

    usuarios = (
        User.query
        .order_by(User.nombre.asc())
        .all()
    )

    return render_template(
        "admin/usuarios.html",
        usuarios=usuarios
    )


# ==========================================================
# CREAR USUARIO
# ==========================================================

@admin_bp.route(
    "/usuarios/nuevo",
    methods=["GET", "POST"]
)
def nuevo_usuario():

    if not administrador_requerido():
        return redirect("/")

    roles = (
        Role.query
        .order_by(Role.nombre.asc())
        .all()
    )

    tiendas = (
        Store.query
        .order_by(Store.nombre.asc())
        .all()
    )

    supervisores = (
        Supervisor.query
        .order_by(Supervisor.nombre.asc())
        .all()
    )

    asesoras = (
        Advisor.query
        .order_by(Advisor.nombre.asc())
        .all()
    )

    if request.method == "POST":

        nombre = request.form.get(
            "nombre",
            ""
        ).strip()

        correo = request.form.get(
            "correo",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        role_id = request.form.get("role_id")

        store_id = request.form.get("store_id")

        supervisor_id = request.form.get(
            "supervisor_id"
        )

        advisor_id = request.form.get(
            "advisor_id"
        )

        activo = request.form.get("activo")


        # ==================================================
        # VALIDACIONES
        # ==================================================

        if not nombre or not correo or not password or not role_id:

            flash(
                "Nombre, correo, contraseña y rol son obligatorios.",
                "danger"
            )

            return render_template(
                "admin/nuevo_usuario.html",
                roles=roles,
                tiendas=tiendas,
                supervisores=supervisores,
                asesoras=asesoras
            )


        # ==================================================
        # CORREO EXISTENTE
        # ==================================================

        usuario_existente = (
            User.query
            .filter_by(correo=correo)
            .first()
        )

        if usuario_existente:

            flash(
                "Ya existe un usuario con ese correo.",
                "danger"
            )

            return render_template(
                "admin/nuevo_usuario.html",
                roles=roles,
                tiendas=tiendas,
                supervisores=supervisores,
                asesoras=asesoras
            )


        # ==================================================
        # CREAR USUARIO
        # ==================================================

        nuevo = User(

            nombre=nombre,

            correo=correo,

            password=generate_password_hash(
                password
            ),

            role_id=int(role_id),

            store_id=(
                int(store_id)
                if store_id
                else None
            ),

            supervisor_id=(
                int(supervisor_id)
                if supervisor_id
                else None
            ),

            advisor_id=(
                int(advisor_id)
                if advisor_id
                else None
            ),

            activo=(activo == "1")
        )


        db.session.add(nuevo)
        db.session.commit()


        flash(
            "Usuario creado correctamente.",
            "success"
        )

        return redirect(
            f"/admin/usuarios/{nuevo.id}/editar"
        )


    return render_template(
        "admin/nuevo_usuario.html",
        roles=roles,
        tiendas=tiendas,
        supervisores=supervisores,
        asesoras=asesoras
    )


# ==========================================================
# EDITAR USUARIO
# ==========================================================

@admin_bp.route(
    "/usuarios/<int:user_id>/editar",
    methods=["GET", "POST"]
)
def editar_usuario(user_id):

    if not administrador_requerido():
        return redirect("/")

    usuario = User.query.get_or_404(user_id)


    roles = (
        Role.query
        .order_by(Role.nombre.asc())
        .all()
    )

    tiendas = (
        Store.query
        .order_by(Store.nombre.asc())
        .all()
    )

    supervisores = (
        Supervisor.query
        .order_by(Supervisor.nombre.asc())
        .all()
    )

    asesoras = (
        Advisor.query
        .order_by(Advisor.nombre.asc())
        .all()
    )


    # ======================================================
    # GUARDAR CAMBIOS
    # ======================================================

    if request.method == "POST":

        nombre = request.form.get(
            "nombre",
            ""
        ).strip()

        correo = request.form.get(
            "correo",
            ""
        ).strip().lower()

        role_id = request.form.get(
            "role_id"
        )

        store_id = request.form.get(
            "store_id"
        )

        supervisor_id = request.form.get(
            "supervisor_id"
        )

        advisor_id = request.form.get(
            "advisor_id"
        )

        activo = request.form.get(
            "activo"
        )


        # ==================================================
        # VALIDAR
        # ==================================================

        if not nombre or not correo or not role_id:

            flash(
                "Nombre, correo y rol son obligatorios.",
                "danger"
            )

            return render_template(
                "admin/editar_usuario.html",
                usuario=usuario,
                roles=roles,
                tiendas=tiendas,
                supervisores=supervisores,
                asesoras=asesoras
            )


        # ==================================================
        # VALIDAR CORREO
        # ==================================================

        usuario_existente = (
            User.query
            .filter(
                User.correo == correo,
                User.id != usuario.id
            )
            .first()
        )

        if usuario_existente:

            flash(
                "Ese correo ya pertenece a otro usuario.",
                "danger"
            )

            return render_template(
                "admin/editar_usuario.html",
                usuario=usuario,
                roles=roles,
                tiendas=tiendas,
                supervisores=supervisores,
                asesoras=asesoras
            )


        # ==================================================
        # ACTUALIZAR
        # ==================================================

        usuario.nombre = nombre

        usuario.correo = correo

        usuario.role_id = int(role_id)

        usuario.store_id = (
            int(store_id)
            if store_id
            else None
        )

        usuario.supervisor_id = (
            int(supervisor_id)
            if supervisor_id
            else None
        )

        usuario.advisor_id = (
            int(advisor_id)
            if advisor_id
            else None
        )

        usuario.activo = (
            activo == "1"
        )


        db.session.commit()


        flash(
            "Usuario actualizado correctamente.",
            "success"
        )

        return redirect(
            f"/admin/usuarios/{usuario.id}/editar"
        )


    # ======================================================
    # MOSTRAR FORMULARIO
    # ======================================================

    return render_template(
        "admin/editar_usuario.html",
        usuario=usuario,
        roles=roles,
        tiendas=tiendas,
        supervisores=supervisores,
        asesoras=asesoras
    )


# ==========================================================
# TIENDAS
# ==========================================================

# ==========================================================
# TIENDAS
# ==========================================================

@admin_bp.route("/tiendas")
def tiendas():

    if not administrador_requerido():
        return redirect("/")

    # ======================================================
    # PERÍODO ACTUAL
    # ======================================================

    anio = request.args.get(
        "anio",
        type=int
    )

    mes = request.args.get(
        "mes",
        type=int
    )

    # Si no llega período, buscar el último disponible
    if not anio or not mes:

        ultimo = (
            db.session.query(
                func.max(Compliance.anio)
            )
            .first()
        )

        if ultimo and ultimo[0]:

            anio = int(ultimo[0])

            mes = (
                db.session.query(
                    func.max(Compliance.mes)
                )
                .filter(
                    Compliance.anio == anio
                )
                .scalar()
            )

            if mes:
                mes = int(mes)

    # ======================================================
    # PERÍODO ANTERIOR
    # ======================================================

    anio_anterior = anio
    mes_anterior = mes - 1 if mes else None

    if mes_anterior == 0:

        mes_anterior = 12

        if anio_anterior:
            anio_anterior -= 1

    # ======================================================
    # TIENDAS
    # ======================================================

    tiendas_db = (
        Store.query
        .filter(
            Store.estado == "ACTIVA"
        )
        .order_by(
            Store.codigo.asc()
        )
        .all()
    )

    # ======================================================
    # RANKING ACTUAL
    # ======================================================

    ranking_actual_query = (
        db.session.query(
            Compliance.store_id,
            func.avg(
                Compliance.cumplimiento_pct
            ).label("cumplimiento")
        )
        .filter(
            Compliance.anio == anio,
            Compliance.mes == mes
        )
        .group_by(
            Compliance.store_id
        )
        .order_by(
            func.avg(
                Compliance.cumplimiento_pct
            ).desc()
        )
        .all()
    )

    ranking_actual = {}

    for posicion, item in enumerate(
        ranking_actual_query,
        1
    ):

        ranking_actual[item.store_id] = {
            "posicion": posicion,
            "cumplimiento": float(
                item.cumplimiento or 0
            )
        }

    # ======================================================
    # RANKING ANTERIOR
    # ======================================================

    ranking_anterior_query = (
        db.session.query(
            Compliance.store_id,
            func.avg(
                Compliance.cumplimiento_pct
            ).label("cumplimiento")
        )
        .filter(
            Compliance.anio == anio_anterior,
            Compliance.mes == mes_anterior
        )
        .group_by(
            Compliance.store_id
        )
        .order_by(
            func.avg(
                Compliance.cumplimiento_pct
            ).desc()
        )
        .all()
    )

    ranking_anterior = {}

    for posicion, item in enumerate(
        ranking_anterior_query,
        1
    ):

        ranking_anterior[item.store_id] = {
            "posicion": posicion,
            "cumplimiento": float(
                item.cumplimiento or 0
            )
        }

    # ======================================================
    # PREPARAR TARJETAS
    # ======================================================

    tarjetas = []

    for tienda in tiendas_db:

        actual = ranking_actual.get(
            tienda.id,
            {}
        )

        anterior = ranking_anterior.get(
            tienda.id,
            {}
        )

        cumplimiento = float(
            actual.get(
                "cumplimiento",
                0
            )
        )

        posicion_actual = actual.get(
            "posicion"
        )

        posicion_anterior = anterior.get(
            "posicion"
        )

        cumplimiento_anterior = float(
            anterior.get(
                "cumplimiento",
                0
            )
        )

        # ==================================================
        # CAMBIO DE CUMPLIMIENTO
        # ==================================================

        cambio_cumplimiento = (
            cumplimiento -
            cumplimiento_anterior
        )

        # ==================================================
        # CAMBIO DE POSICIÓN
        # ==================================================

        if (
            posicion_actual is not None
            and posicion_anterior is not None
        ):

            cambio_posicion = (
                posicion_anterior -
                posicion_actual
            )

        else:

            cambio_posicion = 0

        # ==================================================
        # TEXTO DE EVOLUCIÓN
        # ==================================================

        if cambio_posicion > 0:

            evolucion_posicion = "subio"

        elif cambio_posicion < 0:

            evolucion_posicion = "bajo"

        else:

            evolucion_posicion = "igual"

        # ==================================================
        # EVOLUCIÓN CUMPLIMIENTO
        # ==================================================

        if cambio_cumplimiento > 0.001:

            evolucion_cumplimiento = "mejoro"

        elif cambio_cumplimiento < -0.001:

            evolucion_cumplimiento = "empeoro"

        else:

            evolucion_cumplimiento = "igual"

        # ==================================================
        # IMAGEN
        # ==================================================

        codigo = (
            tienda.codigo or ""
        ).strip()

        # Normalizamos espacios para que
        # S 04 -> S-04
        codigo_imagen = (
            codigo
            .replace(" ", "-")
            .replace("_", "-")
            .upper()
        )

        imagen = (
            f"img/tiendas/{codigo_imagen}.jpg"
        )

        tarjetas.append({

            "id": tienda.id,

            "codigo": tienda.codigo,

            "nombre": tienda.nombre,

            "imagen": imagen,

            "cumplimiento":
                cumplimiento,

            "cumplimiento_anterior":
                cumplimiento_anterior,

            "cambio_cumplimiento":
                cambio_cumplimiento,

            "posicion":
                posicion_actual,

            "posicion_anterior":
                posicion_anterior,

            "cambio_posicion":
                cambio_posicion,

            "evolucion_posicion":
                evolucion_posicion,

            "evolucion_cumplimiento":
                evolucion_cumplimiento

        })

    # ======================================================
    # RENDER
    # ======================================================

    return render_template(

        "admin/tiendas.html",

        tiendas=tarjetas,

        anio=anio,

        mes=mes,

        anio_anterior=anio_anterior,

        mes_anterior=mes_anterior
    )


# ==========================================================
# SUPERVISORES
# ==========================================================

@admin_bp.route("/supervisores")
def supervisores():

    if not administrador_requerido():
        return redirect("/")

    supervisores = (
        Supervisor.query
        .order_by(Supervisor.nombre.asc())
        .all()
    )

    return render_template(
        "admin/supervisores.html",
        supervisores=supervisores
    )


# ==========================================================
# ASESORAS
# ==========================================================

@admin_bp.route("/asesoras")
def asesoras():

    if not administrador_requerido():
        return redirect("/")

    asesoras = (
        Advisor.query
        .order_by(Advisor.nombre.asc())
        .all()
    )

    return render_template(
        "admin/asesoras.html",
        asesoras=asesoras
    )