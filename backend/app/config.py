import os
from dotenv import load_dotenv

load_dotenv()


class Config:

    # Sin valor por defecto en el código: se define en el .env (ver .env.example).
    SECRET_KEY = os.getenv("SECRET_KEY")

    # Correos con permisos especiales: se leen del .env, nunca se escriben en el código.
    CUADRANTE_EMAIL_PERMITIDO = os.getenv("CUADRANTE_EMAIL_PERMITIDO", "")

    CORREOS_SUPERVISORAS = [
        c.strip().lower()
        for c in os.getenv("CORREOS_SUPERVISORAS", "").split(",")
        if c.strip()
    ]

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+psycopg2://"
        f"{os.getenv('DB_USER')}:"
        f"{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:"
        f"{os.getenv('DB_PORT')}/"
        f"{os.getenv('DB_NAME')}"
        f"?client_encoding=utf8"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    OPENWEATHER_API_KEY = os.getenv(
        "OPENWEATHER_API_KEY"
    )

    TOMTOM_API_KEY = os.getenv(
        "TOMTOM_API_KEY"
    )

    GEO_V2_EXTERNAL_TTL = 600

    GEO_V2_TRAFFIC_TTL = 300

    GEO_V2_EXTERNAL_TIMEOUT = 5

    GEO_V2_INCIDENT_RADIUS_KM = 3

