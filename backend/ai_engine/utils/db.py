"""Conexion a BD solo lectura para AI.""""""
Conexion a base de datos solo lectura para AI.
Utiliza SQLAlchemy Core para consultas eficientes.
"""

from sqlalchemy import create_engine
from ai_engine.config import DB_URI


def get_engine():
    """
    Crea y devuelve un motor de SQLAlchemy con parametros adecuados
    para consultas analiticas de solo lectura.
    """
    engine = create_engine(
        DB_URI,
        pool_pre_ping=True,       # Verifica conexiones antes de usar
        isolation_level="READ COMMITTED",  # No bloquea escrituras
        pool_size=3,              # Pocas conexiones para no competir con la app
        max_overflow=2,
        echo=False
    )
    return engine