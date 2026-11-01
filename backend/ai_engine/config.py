"""Configuración para la capa AI de L&H SCORE.
Se conecta a la misma base de datos PostgreSQL usando variables de entorno.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.engine import URL

# En producción, las variables reales del proceso tienen prioridad sobre .env.
load_dotenv(
    Path(__file__).resolve().parent.parent / ".env",
    override=False,
)

# URI de conexión a PostgreSQL
DB_URI = URL.create(
    "postgresql+psycopg2",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME"),
)

# Rutas de datos
BASE_DIR = Path(__file__).resolve().parent
DATA_RAW = BASE_DIR / "data" / "raw"
DATA_PROCESSED = BASE_DIR / "data" / "processed"
DATA_MODELS = BASE_DIR / "data" / "models"

# Asegurar que existan las carpetas
for path in [DATA_RAW, DATA_PROCESSED, DATA_MODELS]:
    path.mkdir(parents=True, exist_ok=True)
