import pandas as pd

from app.extensions import db
from app.models import Store


def importar_tiendas(ruta):

    df = pd.read_excel(
        ruta,
        sheet_name="CUMPL",
        header=2
    )

    creadas = 0

    for _, fila in df.iterrows():

        codigo = fila["Unnamed: 0"]
        nombre = fila["TIENDA"]

        if pd.isna(codigo):
            continue

        codigo = str(codigo).strip()
        nombre = str(nombre).strip()

        # Ignorar filas de resumen
        if (
            codigo == ""
            or "TOTAL" in codigo.upper()
            or "TOTAL" in nombre.upper()
            or "TIENDA VIRTUAL" in nombre.upper()
        ):
            continue

        tienda = Store.query.filter_by(
            codigo=codigo
        ).first()

        if tienda:

            tienda.nombre = nombre

        else:

            tienda = Store(
                codigo=codigo,
                nombre=nombre
            )

            db.session.add(tienda)

            creadas += 1

    db.session.commit()

    return creadas