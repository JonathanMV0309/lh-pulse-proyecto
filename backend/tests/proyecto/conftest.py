"""Pruebas del Sprint 2 (metas de tienda). No arrancan app/__init__.py: usan SQLite en memoria y datos inventados.

Ejecutar desde backend/:  python -m pytest tests/proyecto -v
"""
import sys
import types
from datetime import date, datetime
from pathlib import Path

import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parents[2]
if "app" not in sys.modules or not hasattr(sys.modules["app"], "__path__"):
    paquete = types.ModuleType("app")
    paquete.__path__ = [str(ROOT / "app")]
    sys.modules["app"] = paquete

from app.extensions import db  # noqa: E402
from app.metas.configuracion import ConfiguracionMetas  # noqa: E402
from app.models import Compliance, Role, Store, User  # noqa: E402
from app.models.meta_tienda import MetaTienda  # noqa: E402

HOY = date.today()


@pytest.fixture(autouse=True)
def configuracion_limpia(monkeypatch):
    for k in ("METAS_ORIGEN_DATOS", "METAS_SEMAFORO", "METAS_UMBRAL_VERDE", "METAS_UMBRAL_AMARILLO"):
        monkeypatch.delenv(k, raising=False)
    ConfiguracionMetas.reiniciar()
    yield
    ConfiguracionMetas.reiniciar()


@pytest.fixture
def app():
    from app.metas.api import api_metas_bp
    from app.metas.paginas import metas_paginas_bp
    aplicacion = Flask(__name__, template_folder=str(ROOT / "app" / "templates"))
    aplicacion.config.update(TESTING=True, SECRET_KEY="clave-solo-para-pruebas", SQLALCHEMY_DATABASE_URI="sqlite://")
    db.init_app(aplicacion)
    aplicacion.register_blueprint(api_metas_bp)
    aplicacion.register_blueprint(metas_paginas_bp)
    with aplicacion.app_context():
        db.create_all()
        admin, tienda = Role(id=1, nombre="Administrador"), Role(id=2, nombre="TIENDA")
        db.session.add_all([admin, tienda,
                            Store(id=1, codigo="S-01", nombre="Tienda Norte Ejemplo", ciudad="Bogotá", estado="ACTIVA"),
                            Store(id=2, codigo="S-02", nombre="Tienda Sur Ejemplo", ciudad="Cali", estado="ACTIVA"),
                            Store(id=3, codigo="S-99", nombre="Tienda Cerrada Ejemplo", estado="INACTIVA")])
        db.session.flush()
        db.session.add_all([User(id=1, nombre="Admin Ejemplo", correo="admin@ejemplo.test", password="x", role_id=1),
                            User(id=2, nombre="Tienda Norte", correo="t1@ejemplo.test", password="x", role_id=2, store_id=1)])
        # Dos informes de la S-01 en el mes: debe tomarse el del día de corte más reciente
        for corte, venta in [(10, 4_000_000), (20, 9_000_000)]:
            db.session.add(Compliance(store_id=1, anio=HOY.year, mes=HOY.month, dia_corte=corte, venta_actual=venta,
                                      es_cierre=False, activo=True, fecha_carga=datetime(2026, 1, 1)))
        db.session.add(MetaTienda(store_id=1, anio=HOY.year, mes=HOY.month, valor=20_000_000, actualizado_por="Prueba"))
        db.session.commit()
        aplicacion.extensions.pop("metas_fabrica", None)
        yield aplicacion
        db.session.remove()
        db.drop_all()


def _cliente(app, usuario_id, rol):
    c = app.test_client()
    with c.session_transaction() as s:
        s["user_id"], s["rol"], s["nombre"] = usuario_id, rol, "Admin Ejemplo"
    return c


@pytest.fixture
def admin(app):
    return _cliente(app, 1, "Administrador")


@pytest.fixture
def tienda(app):
    return _cliente(app, 2, "TIENDA")
