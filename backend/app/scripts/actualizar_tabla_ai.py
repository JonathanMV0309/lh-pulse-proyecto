# app/scripts/recrear_tabla_ai.py

from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    # Eliminar tabla antigua
    db.session.execute(text("DROP TABLE IF EXISTS ai_forecast_results;"))
    db.session.commit()

    # Crear tabla con columnas correctas
    db.session.execute(text("""
        CREATE TABLE ai_forecast_results (
            id SERIAL PRIMARY KEY,
            store_id INTEGER,
            line_id INTEGER,
            anio INTEGER,
            mes INTEGER,
            venta_predicha NUMERIC(12,2),
            fecha_generacion TIMESTAMP DEFAULT NOW(),
            modelo_version VARCHAR(100)
        );
    """))
    db.session.commit()
    print("Tabla ai_forecast_results recreada con esquema correcto.")