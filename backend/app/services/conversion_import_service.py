from app.utils.logs import log_debug
import pandas as pd

from app.extensions import db
from app.models.store import Store
from app.models.conversion_diaria import ConversionDiaria


def importar_conversion_diaria(ruta):

    log_debug("=" * 50)
    log_debug("LEYENDO CONVERSIÓN_x_DIA")
    log_debug("=" * 50)

    df = pd.read_excel(
        ruta,
        sheet_name="CONVERSIÓN_x_DIA",
        header=None
    )

    registros = []

    # ==================================================
    # MAPEAR TIENDAS UNA SOLA VEZ
    # ==================================================

    tiendas = {
        str(t.codigo).strip(): t
        for t in Store.query.all()
        if t.codigo
    }

    log_debug(f"Tiendas encontradas en BD: {len(tiendas)}")

    # ==================================================
    # LAS FECHAS ESTÁN EN LA FILA 3
    #
    # DÍA 1:
    # columna 5 = TRAF
    # columna 6 = FACT
    # columna 7 = CONV
    #
    # DÍA 2:
    # columna 8 = TRAF
    # columna 9 = FACT
    # columna 10 = CONV
    #
    # etc.
    # ==================================================

    for col in range(5, df.shape[1], 3):

        fecha = df.iloc[3, col]

        if pd.isna(fecha):
            continue

        try:
            fecha = pd.to_datetime(fecha)
        except Exception:
            print(
                f"[ADVERTENCIA] Fecha inválida columna {col}: {fecha}"
            )
            continue

        anio = int(fecha.year)
        mes = int(fecha.month)
        dia = int(fecha.day)

        log_debug(
            f"Procesando {dia:02d}/{mes:02d}/{anio}..."
        )

        # ==================================================
        # RECORRER SOLO LAS FILAS DE TIENDAS
        #
        # Fila 4 = encabezados
        # Fila 5 en adelante = tiendas
        # ==================================================

        for fila in range(5, df.shape[0]):

            codigo = df.iloc[fila, 1]

            if pd.isna(codigo):
                continue

            codigo = str(codigo).strip()

            # ==================================================
            # VALIDAR QUE REALMENTE SEA UN CÓDIGO DE TIENDA
            # ==================================================

            if not codigo.startswith("S-"):
                continue

            tienda = tiendas.get(codigo)

            if not tienda:
                log_debug(
                    f"[ADVERTENCIA] Tienda no encontrada: {codigo}"
                )
                continue

            # ==================================================
            # DATOS DEL DÍA
            # ==================================================

            trafico = df.iloc[fila, col]
            facturas = df.iloc[fila, col + 1]
            conversion = df.iloc[fila, col + 2]

            # Si no hay tráfico ni facturas, no crear registro
            if pd.isna(trafico) and pd.isna(facturas):
                continue

            # ==================================================
            # CONVERTIR TRÁFICO
            # ==================================================

            try:
                trafico = (
                    int(float(trafico))
                    if not pd.isna(trafico)
                    else 0
                )
            except (ValueError, TypeError):
                trafico = 0

            # ==================================================
            # CONVERTIR FACTURAS
            # ==================================================

            try:
                facturas = (
                    int(float(facturas))
                    if not pd.isna(facturas)
                    else 0
                )
            except (ValueError, TypeError):
                facturas = 0

            # ==================================================
            # CONVERTIR CONVERSIÓN
            # ==================================================

            try:
                conversion = (
                    float(conversion)
                    if not pd.isna(conversion)
                    else 0
                )
            except (ValueError, TypeError):
                conversion = 0

            # ==================================================
            # CREAR REGISTRO
            # ==================================================

            registros.append(
                ConversionDiaria(
                    store_id=tienda.id,
                    anio=anio,
                    mes=mes,
                    dia=dia,
                    trafico=trafico,
                    facturas=facturas,
                    conversion=conversion
                )
            )

    # ==================================================
    # GUARDAR
    # ==================================================

    if registros:

        db.session.add_all(registros)

        db.session.commit()

    log_debug("=" * 50)
    log_debug("CONVERSIÓN DIARIA IMPORTADA")
    log_debug("=" * 50)
    log_debug(f"Registros creados: {len(registros)}")

    return registros