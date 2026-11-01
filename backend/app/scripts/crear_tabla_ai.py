# app/scripts/crear_tabla_ai.py

from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS ai_forecast_results (
            id SERIAL PRIMARY KEY,
            store_id INTEGER,
            anio INTEGER,
            mes INTEGER,
            forecast_value NUMERIC(12,2),
            created_at TIMESTAMP DEFAULT NOW()
        );
    """))
    db.session.commit()
    print("Tabla 'ai_forecast_results' creada correctamente (o ya existente).")