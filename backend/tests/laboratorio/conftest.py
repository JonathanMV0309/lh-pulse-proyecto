"""Entorno aislado para las pruebas del Laboratorio #2.

- No ejecuta app/__init__.py (no arranca IA, ni APIs externas, ni PostgreSQL).
- Usa SQLite en memoria y datos 100 % inventados (tiendas S-01, S-02, correos @ejemplo.test).

Ejecutar desde backend/:  python -m pytest tests/laboratorio -v
"""
import sys
import types
from datetime import datetime
from pathlib import Path

import pytest
from flask import Blueprint, Flask
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[2]

# Paquete "app" sin su __init__ (igual que tests/test_trafico.py del proyecto).
if "app" not in sys.modules or not hasattr(sys.modules["app"], "__path__"):
    paquete = types.ModuleType("app")
    paquete.__path__ = [str(ROOT / "app")]
    sys.modules["app"] = paquete

from app.extensions import db  # noqa: E402
from app.models import (  # noqa: E402
    Advisor,
    AdvisorPerformance,
    Compliance,
    Role,
    Store,
    User,
)
from app.models.registro_acceso import RegistroAcceso  # noqa: E402,F401
from app.routes.auth import auth_bp  # noqa: E402
from app.routes.import_excel import import_excel_bp  # noqa: E402
from app.routes.ranking import ranking_desempeno_bp  # noqa: E402
from app.utils.permissions import admin_required  # noqa: E402

CLAVE = "Clave-Prueba-123"
ANIO, MES, CORTE = 2026, 10, 20


def _sembrar():
    db.session.add_all([
        Role(id=1, nombre="Administrador"),
        Role(id=2, nombre="TIENDA"),
        Role(id=3, nombre="ASESORA"),
        Role(id=4, nombre="ADMINISTRADOR"),
        Store(id=1, codigo="S-01", nombre="Tienda Norte Ejemplo", estado="ACTIVA"),
        Store(id=2, codigo="S-02", nombre="Tienda Sur Ejemplo", estado="ACTIVA"),
        Store(id=3, codigo="TOTA", nombre="TOTAL", estado="ACTIVA"),
        Store(id=4, codigo="S-24", nombre="Tienda Cerrada Ejemplo", estado="ACTIVA"),
    ])
    db.session.flush()
    clave = generate_password_hash(CLAVE)
    db.session.add_all([
        User(id=1, nombre="Admin Ejemplo", correo="admin@ejemplo.test", password=clave, role_id=1),
        User(id=2, nombre="Tienda Norte", correo="tienda01@ejemplo.test", password=clave, role_id=2, store_id=1),
        User(id=3, nombre="Asesora Ejemplo", correo="asesora@ejemplo.test", password=clave, role_id=3),
        User(id=4, nombre="Admin Inactivo", correo="inactivo@ejemplo.test", password=clave, role_id=1, activo=False),
        User(id=5, nombre="Admin Mayúsculas", correo="admin2@ejemplo.test", password=clave, role_id=4),
    ])
    ahora = datetime(2026, 10, 21, 8, 0)
    # Cumplimiento por tienda (cifras inventadas)
    for store_id, venta, pct in [(1, 9_000_000, 0.90), (2, 12_000_000, 1.20), (3, 99_000_000, 9.9), (4, 5_000_000, 2.0)]:
        db.session.add(Compliance(
            store_id=store_id, anio=ANIO, mes=MES, dia_corte=CORTE, venta_actual=venta,
            venta_anterior=venta * 0.8, incremento=0.25, cumplimiento_pct=pct, facturas=100,
            ticket_promedio=venta / 100, es_cierre=False, activo=True, fecha_carga=ahora,
        ))
    db.session.add_all([
        Advisor(id=1, nombre="Ana Ejemplo", store_id=1),
        Advisor(id=2, nombre="Bea Ejemplo", store_id=1),
        Advisor(id=3, nombre="Carla Ejemplo", store_id=2),
    ])
    db.session.flush()
    for advisor_id, store_id, venta, facturas, unidades in [
        (1, 1, 4_000_000, 40, 80),
        (2, 1, 3_000_000, 30, 45),
        (3, 2, 5_000_000, 50, 150),
    ]:
        db.session.add(AdvisorPerformance(
            advisor_id=advisor_id, store_id=store_id, anio=ANIO, mes=MES, dia_corte=CORTE,
            venta=venta, facturas=facturas, unidades=unidades,
        ))
    db.session.commit()


@pytest.fixture
def app():
    aplicacion = Flask(
        __name__,
        template_folder=str(ROOT / "app" / "templates"),
        static_folder=str(ROOT / "app" / "static"),
    )
    aplicacion.config.update(
        SECRET_KEY="solo-pruebas",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        TESTING=True,
    )
    db.init_app(aplicacion)
    aplicacion.register_blueprint(auth_bp)
    aplicacion.register_blueprint(ranking_desempeno_bp)
    aplicacion.register_blueprint(import_excel_bp)

    # Destino de la redirección tras importar (en la app real es el dashboard).
    dashboard = Blueprint("dashboard", __name__)
    dashboard.add_url_rule("/dashboard", "dashboard", lambda: "dashboard")
    aplicacion.register_blueprint(dashboard)

    # Vista mínima protegida para probar el decorador admin_required.
    @aplicacion.route("/solo-admin")
    @admin_required
    def solo_admin():
        return "contenido de administrador"

    with aplicacion.app_context():
        db.create_all()
        _sembrar()
        yield aplicacion
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def iniciar_sesion(client, user_id, rol):
    with client.session_transaction() as sesion:
        sesion["user_id"] = user_id
        sesion["rol"] = rol


def mensajes_flash(client):
    with client.session_transaction() as sesion:
        return [texto for _, texto in sesion.get("_flashes", [])]
