from app.utils.logs import log_debug
import pandas as pd

from app.extensions import db
from app.models import Store, Line, MetaLine


# ==========================================================
# CONFIGURACIÓN DE LÍNEAS
# ==========================================================

CONFIG_LINEAS = {
    "FEMENINO": {
        "meta": "META",
        "meta_proporcional": "META\nPROPORC.",
        "venta": "VENTA",
        "cumplimiento": "CUMPL."
    },

    "PLUS-SIZE": {
        "meta": "META.1",
        "meta_proporcional": "META\nPROPORC..1",
        "venta": "VENTA.1",
        "cumplimiento": "CUMPL..1"
    },

    "MASCULINO": {
        "meta": "META.2",
        "meta_proporcional": "META\nPROPORC..2",
        "venta": "VENTA.2",
        "cumplimiento": "CUMPL..2"
    },

    "ACCESORIOS": {
        "meta": "META.3",
        "meta_proporcional": "META\nPROPORC..3",
        "venta": "VENTA.3",
        "cumplimiento": "CUMPL..3"
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
# IMPORTAR METAS POR LÍNEA
# ==========================================================

def importar_metas_linea(ruta):

    log_debug("=" * 50)
    log_debug("LEYENDO METAS_x_LINEA")
    log_debug("=" * 50)

    df = pd.read_excel(
        ruta,
        sheet_name="METAS_x_LINEA",
        header=3
    )

    # ======================================================
    # BORRAR IMPORTACIÓN ANTERIOR
    # ======================================================

    MetaLine.query.filter_by(
        anio=2026,
        mes=7
    ).delete()

    db.session.commit()

    contador = 0
    tiendas_procesadas = 0

    # ======================================================
    # RECORRER EXCEL
    # ======================================================

    for _, fila in df.iterrows():

        codigo = fila["Unnamed: 0"]

        if pd.isna(codigo):
            continue

        codigo = str(codigo).strip()

        if not codigo:
            continue

        nombre_tienda = str(
            fila["TIENDA"]
        ).strip()

        # ==================================================
        # IGNORAR FILAS QUE NO SON TIENDAS
        # ==================================================

        if (
            "TOTAL" in codigo.upper()
            or "TOTAL" in nombre_tienda.upper()
            or "TIENDA VIRTUAL" in nombre_tienda.upper()
        ):
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
        # RECORRER LAS 4 LÍNEAS
        # ==================================================

        for nombre_linea, columnas in CONFIG_LINEAS.items():

            linea = Line.query.filter_by(
                nombre=nombre_linea
            ).first()

            if not linea:

                log_debug(
                    f"⚠️ Línea no encontrada: {nombre_linea}"
                )

                continue

            meta = convertir_numero(
                fila[columnas["meta"]]
            )

            meta_proporcional = convertir_numero(
                fila[
                    columnas[
                        "meta_proporcional"
                    ]
                ]
            )

            venta = convertir_numero(
                fila[columnas["venta"]]
            )

            cumplimiento = convertir_numero(
                fila[
                    columnas[
                        "cumplimiento"
                    ]
                ]
            )

            # ==================================================
            # CREAR REGISTRO
            # ==================================================

            registro = MetaLine(

                store_id=tienda.id,

                line_id=linea.id,

                anio=2026,

                mes=7,

                meta=meta,

                meta_proporcional=
                    meta_proporcional,

                venta=venta,

                cumplimiento_pct=
                    cumplimiento
            )

            db.session.add(registro)

            contador += 1

    db.session.commit()

    log_debug("=" * 50)
    log_debug("IMPORTACIÓN TERMINADA")
    log_debug("=" * 50)

    log_debug(
        f"Tiendas procesadas: {tiendas_procesadas}"
    )

    log_debug(
        f"Registros de líneas creados: {contador}"
    )

    return contador