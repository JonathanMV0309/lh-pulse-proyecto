from app.utils.logs import log_debug
import pandas as pd

from app.extensions import db
from app.models import Store, Compliance


def analizar_excel(ruta):
    ...
    return resultado


def importar_cumplimiento(ruta):

    # Leer hoja CUMPL
    df = pd.read_excel(
        ruta,
        sheet_name="CUMPL",
        header=2
    )

    # =====================================
    # BORRAR IMPORTACIÓN ANTERIOR
    # =====================================
    Compliance.query.filter_by(
        anio=2026,
        mes=7
    ).delete()

    db.session.commit()

    contador = 0

    for _, fila in df.iterrows():

        codigo = fila["Unnamed: 0"]

        if pd.isna(codigo):
            continue

        codigo = str(codigo).strip()

        nombre = str(fila["TIENDA"]).strip()

        # Ignorar filas que no son tiendas
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

        if not tienda:
            log_debug("Tienda no encontrada:", codigo)
            continue

        cumplimiento = Compliance(
            store_id=tienda.id,
            anio=2026,
            mes=7,
            venta_actual=fila[2026],
            venta_anterior=fila[2025],
            cumplimiento_pct=fila["CUMPLI\npropor"]
        )

        db.session.add(cumplimiento)

        contador += 1

    db.session.commit()

    return contador