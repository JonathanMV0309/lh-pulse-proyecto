import mimetypes

# Windows puede tener mal registrado el tipo de .js/.css; los módulos JS (Hilo 3D) lo exigen correcto
mimetypes.add_type('text/javascript', '.js')
mimetypes.add_type('text/css', '.css')

from flask import Flask, render_template, redirect, session

from app.config import Config
from app.extensions import db, migrate

# ==========================
# Rutas
# ==========================

from app.routes.import_excel import import_excel_bp
from app.routes.auth import auth_bp
from app.routes.category import category_bp
from app.routes.dashboard import dashboard_bp
from app.routes.admin import admin_bp
from app.routes.admin_goals import admin_goals_bp
from app.routes.app_pages import app_pages_bp
from app.routes.dashboard_geografico import dashboard_geografico_bp
from app.routes.vendedor_unico import vendedor_unico_bp
from app.routes.notifications import notifications_bp
from ai_engine.api.routes_ai import ai_dashboard_bp
from app.routes.cuadrante import cuadrante_bp
from app.routes.checklist import checklist_bp
from app.routes.dashboard_geografico_v2 import dashboard_geografico_v2_bp
from app.routes.trafico import trafico_bp
from app.routes.ranking import ranking_desempeno_bp
from app.routes.accesos import accesos_bp, crear_tabla_si_falta
from app.routes.mensajes_hilo import mensajes_hilo_bp, crear_tablas_si_faltan as crear_tablas_mensajes_hilo
from app.routes.hilo_inteligente import hilo_inteligente_bp
from app.routes.retos import retos_bp
from app.routes.planilla import planilla_bp
from app.routes.novedades import novedades_bp
from app.routes.historico import historico_bp
from app.services.trafico_import_service import importar_trafico, importar_cuenta_personas

# ==========================
# Importar modelos
# ==========================

from app.models import *


def create_app():

    app = Flask(__name__)

    app.config.from_object(Config)

    # ==========================
    # Extensiones
    # ==========================

    db.init_app(app)
    migrate.init_app(app, db)

    # ==========================
    # Registrar Blueprints
    # ==========================

    app.register_blueprint(auth_bp)
    app.register_blueprint(category_bp)
    app.register_blueprint(import_excel_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_goals_bp)
    app.register_blueprint(app_pages_bp)
    app.register_blueprint(dashboard_geografico_bp)
    app.register_blueprint(dashboard_geografico_v2_bp)
    app.register_blueprint(vendedor_unico_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(ai_dashboard_bp)
    app.register_blueprint(cuadrante_bp)
    app.register_blueprint(checklist_bp)
    app.register_blueprint(trafico_bp)
    app.register_blueprint(ranking_desempeno_bp)
    app.register_blueprint(accesos_bp)
    app.register_blueprint(mensajes_hilo_bp)
    app.register_blueprint(hilo_inteligente_bp)
    app.register_blueprint(retos_bp)
    app.register_blueprint(planilla_bp)
    app.register_blueprint(novedades_bp)
    app.register_blueprint(historico_bp)

    # Registro de accesos: crea su tabla si aún no existe (no toca las demás)
    crear_tabla_si_falta(app)
    crear_tablas_mensajes_hilo(app)
    app.cli.add_command(importar_trafico)
    app.cli.add_command(importar_cuenta_personas)

    # ==========================
    # Context processor global
    # ==========================

    @app.context_processor
    def injectar_usuario():
        from app.models.user import User
        if "user_id" in session:
            usuario = User.query.get(session["user_id"])
            return {"usuario": usuario}
        return {"usuario": None}

    # ==========================
    # Ruta principal
    # ==========================

    @app.route("/")
    def home():
        if "user_id" in session:
            return redirect("/dashboard")
        return render_template("login.html")

    return app
