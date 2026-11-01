from app.extensions import db
from app.models import Line


LINEAS = [
    "FEMENINO",
    "PLUS-SIZE",
    "MASCULINO",
    "ACCESORIOS"
]


def crear_lineas():

    creadas = 0

    for nombre in LINEAS:

        linea = Line.query.filter_by(
            nombre=nombre
        ).first()

        if not linea:

            linea = Line(
                nombre=nombre
            )

            db.session.add(linea)

            creadas += 1

    db.session.commit()

    return creadas