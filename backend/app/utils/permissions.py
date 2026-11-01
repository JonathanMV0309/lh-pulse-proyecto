from functools import wraps

from flask import session, redirect, flash


# Nombres con los que el rol de administrador existe en la base de datos.
# Se comparan sin importar mayúsculas ni espacios ("Administrador", "ADMINISTRADOR", "Admin").
ROLES_ADMINISTRADOR = {"ADMIN", "ADMINISTRADOR"}


def normalizar_rol(nombre_rol):
    """Devuelve el nombre del rol en mayúsculas y sin espacios ('' si no hay rol)."""
    return (nombre_rol or "").strip().upper()


def es_administrador(nombre_rol):
    """Única regla del sistema para decidir si un rol tiene permisos de administrador."""
    return normalizar_rol(nombre_rol) in ROLES_ADMINISTRADOR


def login_required(view):
    """
    Verifica que exista un usuario autenticado en la sesión.
    """

    @wraps(view)
    def wrapped_view(*args, **kwargs):

        if "user_id" not in session:

            flash(
                "Debes iniciar sesión para acceder a esta sección.",
                "warning"
            )

            return redirect("/")

        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    """
    Permite el acceso únicamente a usuarios con rol Administrador.
    """

    @wraps(view)
    def wrapped_view(*args, **kwargs):

        # Primero verificar sesión
        if "user_id" not in session:

            flash(
                "Debes iniciar sesión para acceder a esta sección.",
                "warning"
            )

            return redirect("/")

        # Solo Administrador (rol guardado durante el login)
        if not es_administrador(session.get("rol")):

            flash(
                "No tienes permisos para acceder a esta sección.",
                "danger"
            )

            return redirect("/")

        return view(*args, **kwargs)

    return wrapped_view