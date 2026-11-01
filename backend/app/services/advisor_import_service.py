from app.utils.logs import log_debug
import pandas as pd

from app.extensions import db
from app.models import Advisor, AdvisorPerformance, Store


def importar_asesoras(ruta):

    log_debug("=" * 50)
    log_debug("IMPORTANDO ASESORAS Y RENDIMIENTO")
    log_debug("=" * 50)

    # ==================================================
    # LEER EXCEL
    # ==================================================

    df = pd.read_excel(
        ruta,
        sheet_name="UPT_VPT_ASESOR",
        header=2
    )

    # Limpiar espacios de los encabezados
    df.columns = df.columns.astype(str).str.strip()

    log_debug("Columnas detectadas:")
    log_debug(list(df.columns))

    cargados = 0
    rendimiento_cargado = 0

    # ==================================================
    # FUNCION PARA CONVERTIR NUMEROS
    # ==================================================

    def numero(valor):

        if pd.isna(valor):
            return 0.0

        try:
            return float(valor)
        except (ValueError, TypeError):
            return 0.0

    # ==================================================
    # RECORRER REGISTROS
    # ==================================================

    for _, fila in df.iterrows():

        nombre = fila.get("NOMBRE_ASESOR")
        tienda_nombre = fila.get("TIENDA")

        if pd.isna(nombre) or pd.isna(tienda_nombre):
            continue

        nombre = str(nombre).strip()
        tienda_nombre = str(tienda_nombre).strip()

        # Ignorar filas vacías
        if not nombre or not tienda_nombre:
            continue

        if nombre.lower() in [
            "(en blanco)",
            "nan",
            "none"
        ]:
            continue

        if tienda_nombre.lower() in [
            "(en blanco)",
            "nan",
            "none"
        ]:
            continue

        # Ignorar filas Total
        if nombre.lower().startswith("total"):
            continue

        # ==================================================
        # BUSCAR TIENDA POR NOMBRE
        # ==================================================

        tienda = Store.query.filter(
            Store.nombre.ilike(tienda_nombre)
        ).first()

        # ==================================================
        # BUSCAR TIENDA POR CODIGO
        # ==================================================

        if not tienda:

            partes = tienda_nombre.split()

            codigo_numero = None

            if len(partes) >= 2 and partes[0] == "S":
                codigo_numero = partes[1]

            if codigo_numero:

                posibles = Store.query.all()

                for t in posibles:

                    codigo_bd = (
                        str(t.codigo)
                        .replace("S-", "")
                        .replace("S", "")
                        .strip()
                        .zfill(2)
                    )

                    if codigo_bd == codigo_numero.zfill(2):

                        tienda = t
                        break

        # ==================================================
        # SI NO EXISTE LA TIENDA
        # ==================================================

        if not tienda:

            log_debug(
                "Tienda no encontrada:",
                tienda_nombre,
                "| Asesora:",
                nombre
            )

            continue

        # ==================================================
        # BUSCAR / CREAR ASESORA
        # ==================================================

        asesora = Advisor.query.filter_by(
            nombre=nombre,
            store_id=tienda.id
        ).first()

        if not asesora:

            asesora = Advisor(
                nombre=nombre,
                store_id=tienda.id,
                es_generico=False
            )

            db.session.add(asesora)
            db.session.flush()

            cargados += 1

        # ==================================================
        # LEER DATOS
        # ==================================================

        venta = numero(
            fila.get("VAL_FAC_2026")
        )

        unidades = numero(
            fila.get("UNID_FAC_2026")
        )

        facturas = numero(
            fila.get("CANT_FACT_2026")
        )

        ticket = numero(
            fila.get("TICKET $ 2026")
        )

        upt = numero(
            fila.get("TICKET UNID. 2026")
        )

        # ==================================================
        # BUSCAR RENDIMIENTO EXISTENTE
        # ==================================================

        rendimiento = AdvisorPerformance.query.filter_by(
            advisor_id=asesora.id,
            store_id=tienda.id,
            anio=2026,
            mes=7
        ).first()

        # ==================================================
        # ACTUALIZAR
        # ==================================================

        if rendimiento:

            rendimiento.venta = venta
            rendimiento.unidades = unidades
            rendimiento.facturas = facturas
            rendimiento.ticket_promedio = ticket
            rendimiento.upt = upt

        # ==================================================
        # CREAR
        # ==================================================

        else:

            rendimiento = AdvisorPerformance(

                advisor_id=asesora.id,

                store_id=tienda.id,

                anio=2026,

                mes=7,

                venta=venta,

                unidades=unidades,

                facturas=facturas,

                ticket_promedio=ticket,

                upt=upt
            )

            db.session.add(rendimiento)

        rendimiento_cargado += 1

    # ==================================================
    # GUARDAR
    # ==================================================

    db.session.commit()

    log_debug("=" * 50)
    log_debug("IMPORTACION TERMINADA")
    log_debug("=" * 50)

    log_debug(
        "Asesoras nuevas:",
        cargados
    )

    log_debug(
        "Rendimientos procesados:",
        rendimiento_cargado
    )

    return {
        "asesoras": cargados,
        "rendimientos": rendimiento_cargado
    }