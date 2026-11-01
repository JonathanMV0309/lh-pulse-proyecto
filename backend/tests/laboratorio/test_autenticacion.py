"""Módulo 1: login y registro (app/routes/auth.py)."""
from app.models import User

from .conftest import CLAVE, iniciar_sesion


# ---------- Comportamiento normal (debe seguir igual) ----------

def test_login_correcto_crea_la_sesion(client):
    respuesta = client.post("/api/auth/login", json={"correo": "admin@ejemplo.test", "password": CLAVE})

    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert datos["mensaje"] == "Login exitoso"
    assert datos["usuario"] == {"id": 1, "nombre": "Admin Ejemplo", "correo": "admin@ejemplo.test", "rol": "Administrador"}
    with client.session_transaction() as sesion:
        assert sesion["user_id"] == 1
        assert sesion["rol"] == "Administrador"
        assert sesion["nombre"] == "Admin Ejemplo"


def test_logout_limpia_la_sesion(client):
    iniciar_sesion(client, 1, "Administrador")

    respuesta = client.get("/api/auth/logout")

    assert respuesta.status_code == 302
    with client.session_transaction() as sesion:
        assert "user_id" not in sesion


def test_registro_por_administrador_crea_usuario(client):
    iniciar_sesion(client, 1, "Administrador")

    respuesta = client.post("/api/auth/register", json={
        "nombre": "Nueva Tienda", "correo": "nueva@ejemplo.test", "password": CLAVE, "rol": "TIENDA",
    })

    assert respuesta.status_code == 201
    assert User.query.filter_by(correo="nueva@ejemplo.test").one().role.nombre == "TIENDA"


# ---------- Comportamiento de error ----------

def test_login_con_clave_incorrecta_responde_401(client):
    respuesta = client.post("/api/auth/login", json={"correo": "admin@ejemplo.test", "password": "otra"})

    assert respuesta.status_code == 401
    with client.session_transaction() as sesion:
        assert "user_id" not in sesion


def test_login_de_usuario_inexistente_responde_404(client):
    respuesta = client.post("/api/auth/login", json={"correo": "nadie@ejemplo.test", "password": CLAVE})

    assert respuesta.status_code == 404


def test_login_sin_campos_responde_400(client):
    respuesta = client.post("/api/auth/login", json={"correo": "admin@ejemplo.test"})

    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"] == "Correo y contraseña son obligatorios"


def test_login_con_json_que_no_es_objeto_responde_400_y_no_500(client):
    """Antes: request.get_json() devolvía una lista y data.get(...) lanzaba AttributeError (500)."""
    respuesta = client.post("/api/auth/login", json=["admin@ejemplo.test", CLAVE])

    assert respuesta.status_code == 400
    assert respuesta.is_json


def test_login_sin_cuerpo_json_responde_400_en_json(client):
    """Antes: un formulario o un cuerpo vacío daba 415/400 en HTML, que el login.html no sabe leer."""
    respuesta = client.post("/api/auth/login", data={"correo": "admin@ejemplo.test", "password": CLAVE})

    assert respuesta.status_code == 400
    assert respuesta.is_json
    assert "error" in respuesta.get_json()


def test_registro_sin_sesion_es_rechazado(client):
    respuesta = client.post("/api/auth/register", json={"nombre": "X", "correo": "x@ejemplo.test", "password": CLAVE})

    assert respuesta.status_code == 403
    assert User.query.filter_by(correo="x@ejemplo.test").first() is None


def test_registro_por_usuario_tienda_es_rechazado(client):
    iniciar_sesion(client, 2, "TIENDA")

    respuesta = client.post("/api/auth/register", json={"nombre": "X", "correo": "x@ejemplo.test", "password": CLAVE})

    assert respuesta.status_code == 403
