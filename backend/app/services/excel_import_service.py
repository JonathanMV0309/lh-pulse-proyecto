from app.utils.logs import log_debug
import pandas as pd

from app.extensions import db
from app.models import Compliance, Store


def importar_cumplimiento(
    ruta,
    anio,
    mes,
    dia_corte,
    es_cierre=False,
    nombre_archivo=None
):
    """
    Importa la hoja CUMPL de un archivo Excel.

    Cada importación representa un corte específico.

    Ejemplo:

        1-5 JUL  -> dia_corte=5
        1-8 JUL  -> dia_corte=8
        1-15 JUL -> dia_corte=15
        1-31 JUL -> dia_corte=31
    """

    df = pd.read_excel(
        ruta,
        sheet_name="CUMPL",
        header=2
    )

    cargados = 0

    # ==================================================
    # VALIDACIÓN
    # ==================================================

    if not anio:
        raise ValueError(
            "El año del periodo es obligatorio."
        )

    if not mes:
        raise ValueError(
            "El mes del periodo es obligatorio."
        )

    if not dia_corte:
        raise ValueError(
            "El día de corte es obligatorio."
        )

    # ==================================================
    # NORMALIZAR NOMBRE DEL ARCHIVO
    # ==================================================

    if nombre_archivo:
        nombre_archivo = str(nombre_archivo)

    # ==================================================
    # DESACTIVAR EL CORTE ANTERIOR
    #
    # IMPORTANTE:
    #
    # Solo desactivamos registros del mismo
    # periodo que estamos reemplazando.
    #
    # NO eliminamos información.
    # ==================================================

    Compliance.query.filter(
        Compliance.anio == anio,
        Compliance.mes == mes,
        Compliance.activo.is_(True)
    ).update(
        {
            Compliance.activo: False
        },
        synchronize_session=False
    )

    # ==================================================
    # IMPORTAR FILAS
    # ==================================================

    for _, fila in df.iterrows():

        codigo = fila["TIENDA"]

        if pd.isna(codigo):
            continue

        codigo = str(codigo).strip()

        # ==================================================
        # BUSCAR TIENDA
        # ==================================================

        tienda = Store.query.filter_by(
            codigo=codigo
        ).first()

        if not tienda:

            log_debug(
                "Tienda no encontrada:",
                codigo
            )

            continue

        # ==================================================
        # CREAR REGISTRO
        # ==================================================

        registro = Compliance(

            store_id=tienda.id,

            anio=anio,

            mes=mes,

            venta_actual=fila[2026],

            venta_anterior=fila[2025],

            incremento=fila["INC"],

            cuota_proporcional=fila[
                "CUOTA \nPROPORC"
            ],

            cuota_total=fila[
                "CUOTA TOT"
            ],

            cumplimiento_pct=fila[
                "CUMPLI\npropor"
            ],

            falta_para_cuota=fila[
                "FALTA\nPARA CUOTA"
            ],

            venta_promedio_dia=fila[
                "VTA PROM DIA"
            ],

            trafico=fila[
                "2026.1"
            ],

            facturas=fila[
                "2026.2"
            ],

            conversion=fila[
                "2026.3"
            ],

            ticket_promedio=fila[
                "2026.4"
            ],

            # ==========================================
            # CONTROL DEL CORTE
            # ==========================================

            dia_corte=dia_corte,

            es_cierre=es_cierre,

            activo=True,

            nombre_archivo=nombre_archivo

        )

        db.session.add(registro)

        cargados += 1

    # ==================================================
    # GUARDAR
    # ==================================================

    db.session.commit()

    return cargados