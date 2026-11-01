from app.utils.logs import log_debug
import pandas as pd

from app.extensions import db
from app.models import Store, Line
from app.models.sales_history_line import SalesHistoryLine


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

ANIO_ACTUAL = 2026
ANIO_ANTERIOR = 2025
MES = 7


# ==========================================================
# LÍNEAS QUE VAMOS A IMPORTAR
#
# La hoja SUPERVISOR tiene:
#
# TOTAL       columnas 3 - 6
# FEMENINO    columnas 7 - 10
# PLUS-SIZE   columnas 11 - 14
# MASCULINO   columnas 15 - 18
# ACCESORIOS  columnas 19 - 22
#
# Cada bloque:
#
# 2025
# 2026
# DIF
# INCR
# ==========================================================

CONFIG_LINEAS = {

    "FEMENINO": {
        "col_2025": 7,
        "col_2026": 8
    },

    "PLUS-SIZE": {
        "col_2025": 11,
        "col_2026": 12
    },

    "MASCULINO": {
        "col_2025": 15,
        "col_2026": 16
    },

    "ACCESORIOS": {
        "col_2025": 19,
        "col_2026": 20
    }
}


# ==========================================================
# CONVERTIR NÚMEROS
# ==========================================================

def convertir_numero(valor):

    if pd.isna(valor):
        return 0

    try:

        return float(valor)

    except (ValueError, TypeError):

        return 0


# ==========================================================
# IMPORTAR SUPERVISOR
# ==========================================================

def importar_supervisores(ruta):

    log_debug("=" * 60)
    log_debug("LEYENDO SUPERVISOR")
    log_debug("=" * 60)

    # ======================================================
    # LEER EXCEL
    #
    # No usamos header porque tenemos encabezados agrupados.
    # ======================================================

    df = pd.read_excel(
        ruta,
        sheet_name="SUPERVISOR",
        header=None
    )

    # ======================================================
    # BORRAR IMPORTACIÓN ANTERIOR
    #
    # Borramos ambos años del mes correspondiente.
    # ======================================================

    SalesHistoryLine.query.filter(
        SalesHistoryLine.anio.in_([
            ANIO_ANTERIOR,
            ANIO_ACTUAL
        ]),
        SalesHistoryLine.mes == MES
    ).delete(
        synchronize_session=False
    )

    db.session.commit()

    # ======================================================
    # CONTADORES
    # ======================================================

    contador = 0
    tiendas_procesadas = 0

    # ======================================================
    # RECORRER FILAS
    #
    # Los datos empiezan en la fila 5.
    # Índice pandas = 5
    # ======================================================

    for indice, fila in df.iterrows():

        if indice < 5:
            continue

        # ==================================================
        # CÓDIGO TIENDA
        # ==================================================

        codigo = fila.iloc[0]

        if pd.isna(codigo):
            continue

        codigo = str(codigo).strip()

        if not codigo:
            continue

        # ==================================================
        # IGNORAR TOTALES
        # ==================================================

        if "TOTAL" in codigo.upper():
            continue

        # ==================================================
        # BUSCAR TIENDA
        # ==================================================

        tienda = Store.query.filter_by(
            codigo=codigo
        ).first()

        if not tienda:

            log_debug(
                f"⚠️ Tienda no encontrada: {codigo}"
            )

            continue

        tiendas_procesadas += 1

        # ==================================================
        # RECORRER LÍNEAS
        # ==================================================

        for nombre_linea, columnas in CONFIG_LINEAS.items():

            # ==================================================
            # BUSCAR LÍNEA
            # ==================================================

            linea = Line.query.filter_by(
                nombre=nombre_linea
            ).first()

            if not linea:

                log_debug(
                    f"⚠️ Línea no encontrada: "
                    f"{nombre_linea}"
                )

                continue

            # ==================================================
            # VENTA 2025
            # ==================================================

            venta_2025 = convertir_numero(
                fila.iloc[
                    columnas["col_2025"]
                ]
            )

            # ==================================================
            # VENTA 2026
            # ==================================================

            venta_2026 = convertir_numero(
                fila.iloc[
                    columnas["col_2026"]
                ]
            )

            # ==================================================
            # REGISTRO 2025
            # ==================================================

            registro_2025 = SalesHistoryLine(

                store_id=tienda.id,

                line_id=linea.id,

                anio=ANIO_ANTERIOR,

                mes=MES,

                venta=venta_2025
            )

            db.session.add(
                registro_2025
            )

            # ==================================================
            # REGISTRO 2026
            # ==================================================

            registro_2026 = SalesHistoryLine(

                store_id=tienda.id,

                line_id=linea.id,

                anio=ANIO_ACTUAL,

                mes=MES,

                venta=venta_2026
            )

            db.session.add(
                registro_2026
            )

            contador += 2

    # ======================================================
    # GUARDAR
    # ======================================================

    db.session.commit()

    # ======================================================
    # RESULTADO
    # ======================================================

    log_debug("=" * 60)
    log_debug("IMPORTACIÓN SUPERVIS TERMINADA")
    log_debug("=" * 60)

    log_debug(
        f"Tiendas procesadas: "
        f"{tiendas_procesadas}"
    )

    log_debug(
        f"Registros creados: "
        f"{contador}"
    )

    return contador