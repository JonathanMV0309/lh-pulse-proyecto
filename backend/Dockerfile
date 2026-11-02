# API de L&H Pulse (Flask + gunicorn). La base de datos es otro contenedor (ver docker-compose.yml).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Primero las dependencias: así Docker reutiliza esta capa si solo cambia el código
COPY requirements.txt .
RUN pip install -r requirements.txt gunicorn==23.0.0

COPY . .

# Sin privilegios de administrador dentro del contenedor
RUN useradd --create-home lhpulse && chown -R lhpulse /app
USER lhpulse

EXPOSE 5000

# Crea las tablas y siembra datos de ejemplo si la base está vacía; luego levanta la API
CMD ["sh", "-c", "flask --app run sembrar && gunicorn --bind 0.0.0.0:5000 --workers 2 --threads 4 --access-logfile - run:app"]
