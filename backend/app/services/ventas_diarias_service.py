from collections import defaultdict
from datetime import date

from app.models import DailySales, DailyStoreSales, Store


DIAS_SEMANA_ES = {
    "LUNES": "Lunes",
    "MARTES": "Martes",
    "MIERCOLES": "Miércoles",
    "JUEVES": "Jueves",
    "VIERNES": "Viernes",
    "SABADO": "Sábado",
    "DOMINGO": "Domingo",
    "MONDAY": "Lunes",
    "TUESDAY": "Martes",
    "WEDNESDAY": "Miércoles",
    "THURSDAY": "Jueves",
    "FRIDAY": "Viernes",
    "SATURDAY": "Sábado",
    "SUNDAY": "Domingo",
}

NOMBRES_DIAS_ES = (
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
)


def _nombre_dia(anio, mes, dia):
    """Devuelve el día en español sin depender de la configuración regional."""
    try:
        return NOMBRES_DIAS_ES[date(int(anio), int(mes), int(dia)).weekday()]
    except (TypeError, ValueError):
        return "No aplica"


def _ultimo_por_clave(registros, clave):
    resultado = {}
    for registro in registros:
        llave = clave(registro)
        actual = resultado.get(llave)
        corte = int(registro.dia_corte or 0)
        if actual is None or corte > int(actual.dia_corte or 0):
            resultado[llave] = registro
    return list(resultado.values())


def obtener_periodos_ventas_diarias():
    periodos = {
        (int(anio), int(mes))
        for anio, mes in DailySales.query.with_entities(
            DailySales.anio,
            DailySales.mes,
        ).distinct().all()
        if anio and mes
    }
    periodos.update({
        (int(anio), int(mes))
        for anio, mes in DailyStoreSales.query.with_entities(
            DailyStoreSales.anio,
            DailyStoreSales.mes,
        ).distinct().all()
        if anio and mes
    })
    return [
        {"anio": anio, "mes": mes}
        for anio, mes in sorted(periodos, reverse=True)
    ]


def construir_resumen_global(anio, mes, dia_corte=None):
    consulta = DailySales.query.filter(
        DailySales.anio == anio,
        DailySales.mes == mes,
        DailySales.store_id.is_(None),
    )
    if dia_corte is not None:
        consulta = consulta.filter(DailySales.dia_corte <= dia_corte)

    registros = _ultimo_por_clave(
        consulta.order_by(DailySales.dia.asc()).all(),
        lambda registro: registro.dia,
    )
    registros.sort(key=lambda registro: registro.dia)

    dias = []
    total_2025 = 0.0
    total_2026 = 0.0

    for registro in registros:
        venta_2025 = float(registro.venta_2025 or 0)
        venta_2026 = float(registro.venta_2026 or 0)
        tiene_actual = venta_2026 != 0
        diferencia = venta_2026 - venta_2025 if tiene_actual else None
        incremento = (
            diferencia / venta_2025 * 100
            if tiene_actual and venta_2025 > 0
            else (0.0 if tiene_actual else None)
        )

        if tiene_actual:
            total_2025 += venta_2025
            total_2026 += venta_2026

        dias.append({
            "dia": int(registro.dia),
            "venta_2025": venta_2025,
            "venta_2026": venta_2026 if tiene_actual else None,
            "diferencia": diferencia,
            "incremento": incremento,
            "sin_dato_2026": not tiene_actual,
            "dia_semana_2025": DIAS_SEMANA_ES.get(
                registro.dia_semana_2025,
                registro.dia_semana_2025 or "",
            ),
            "dia_semana_2026": DIAS_SEMANA_ES.get(
                registro.dia_semana_2026,
                registro.dia_semana_2026 or "",
            ),
        })

    diferencia_total = total_2026 - total_2025
    incremento_total = (
        diferencia_total / total_2025 * 100 if total_2025 > 0 else 0.0
    )
    comparables = [dia for dia in dias if dia["incremento"] is not None]

    return {
        "ventas_diarias": dias,
        "total_venta_2025": total_2025,
        "total_venta_2026": total_2026,
        "total_diferencia": diferencia_total,
        "total_incremento": incremento_total,
        "mejores_dias": sorted(
            comparables,
            key=lambda item: item["incremento"],
            reverse=True,
        )[:5],
        "peores_dias": sorted(
            comparables,
            key=lambda item: item["incremento"],
        )[:5],
    }


def construir_resumen_tiendas(anio, mes, dia_corte=None, store_id=None):
    consulta = (
        DailyStoreSales.query
        .join(Store, Store.id == DailyStoreSales.store_id)
        .filter(
            DailyStoreSales.anio == anio,
            DailyStoreSales.mes == mes,
        )
    )
    if dia_corte is not None:
        consulta = consulta.filter(DailyStoreSales.dia_corte <= dia_corte)
    if store_id is not None:
        consulta = consulta.filter(DailyStoreSales.store_id == store_id)

    registros = _ultimo_por_clave(
        consulta.all(),
        lambda registro: (registro.store_id, registro.dia),
    )
    registros.sort(key=lambda registro: (registro.store.codigo, registro.dia))

    consulta_anterior = (
        DailyStoreSales.query
        .join(Store, Store.id == DailyStoreSales.store_id)
        .filter(
            DailyStoreSales.anio == anio - 1,
            DailyStoreSales.mes == mes,
        )
    )
    if dia_corte is not None:
        # El corte debe comparar la misma cantidad de días. Se toma la versión
        # más reciente disponible del año anterior para cada día incluido.
        consulta_anterior = consulta_anterior.filter(
            DailyStoreSales.dia <= dia_corte
        )
    if store_id is not None:
        consulta_anterior = consulta_anterior.filter(
            DailyStoreSales.store_id == store_id
        )

    registros_anterior = _ultimo_por_clave(
        consulta_anterior.all(),
        lambda registro: (registro.store_id, registro.dia),
    )
    anterior_por_clave = {
        (registro.store_id, int(registro.dia)): registro
        for registro in registros_anterior
    }

    por_dia = defaultdict(lambda: {
        "venta": 0.0,
        "venta_anterior": 0.0,
        "unidades": 0,
        "registros": 0,
        "registros_anterior": 0,
    })
    por_tienda = defaultdict(lambda: {
        "venta": 0.0,
        "venta_anterior": 0.0,
        "unidades": 0,
        "dias": 0,
        "dias_comparables": 0,
        "mejor_dia": None,
        "mejor_venta": -1.0,
    })
    detalle = []

    for registro in registros:
        venta = float(registro.venta or 0)
        unidades = int(registro.unidades or 0)
        tienda = registro.store
        registro_anterior = anterior_por_clave.get(
            (registro.store_id, int(registro.dia))
        )
        venta_anterior = (
            float(registro_anterior.venta or 0)
            if registro_anterior is not None
            else None
        )
        diferencia = (
            venta - venta_anterior if venta_anterior is not None else None
        )
        crecimiento = (
            diferencia / venta_anterior * 100
            if diferencia is not None and venta_anterior > 0
            else None
        )

        por_dia[int(registro.dia)]["venta"] += venta
        por_dia[int(registro.dia)]["unidades"] += unidades
        por_dia[int(registro.dia)]["registros"] += 1
        if venta_anterior is not None:
            por_dia[int(registro.dia)]["venta_anterior"] += venta_anterior
            por_dia[int(registro.dia)]["registros_anterior"] += 1

        resumen = por_tienda[tienda.id]
        resumen.update({
            "store_id": tienda.id,
            "codigo": tienda.codigo,
            "nombre": tienda.nombre,
            "ciudad": tienda.ciudad or "Sin ciudad",
        })
        resumen["venta"] += venta
        resumen["unidades"] += unidades
        resumen["dias"] += 1
        if venta_anterior is not None:
            resumen["venta_anterior"] += venta_anterior
            resumen["dias_comparables"] += 1
        if venta > resumen["mejor_venta"]:
            resumen["mejor_venta"] = venta
            resumen["mejor_dia"] = int(registro.dia)

        detalle.append({
            "store_id": tienda.id,
            "codigo": tienda.codigo,
            "tienda": tienda.nombre,
            "ciudad": tienda.ciudad or "Sin ciudad",
            "dia": int(registro.dia),
            "dia_semana_anterior": _nombre_dia(
                anio - 1,
                mes,
                registro.dia,
            ),
            "dia_semana_actual": _nombre_dia(
                anio,
                mes,
                registro.dia,
            ),
            "venta": venta,
            "venta_anterior": venta_anterior,
            "diferencia": diferencia,
            "crecimiento": crecimiento,
            "unidades": unidades,
            "valor_unidad": venta / unidades if unidades > 0 else 0.0,
        })

    # Detalle completo de una tienda: el año anterior se muestra hasta el último
    # día del mes; los días que aún no tienen venta actual quedan "pendientes" y
    # se van llenando con cada carga. Los totales siguen contando solo hasta el corte.
    detalle_completo = list(detalle)
    if store_id is not None:
        consulta_anterior_mes = (
            DailyStoreSales.query
            .join(Store, Store.id == DailyStoreSales.store_id)
            .filter(
                DailyStoreSales.anio == anio - 1,
                DailyStoreSales.mes == mes,
                DailyStoreSales.store_id == store_id,
            )
        )
        con_venta_actual = {(item["store_id"], item["dia"]) for item in detalle}
        for registro in _ultimo_por_clave(
            consulta_anterior_mes.all(),
            lambda registro: (registro.store_id, registro.dia),
        ):
            if (registro.store_id, int(registro.dia)) in con_venta_actual:
                continue
            tienda = registro.store
            detalle_completo.append({
                "store_id": tienda.id,
                "codigo": tienda.codigo,
                "tienda": tienda.nombre,
                "ciudad": tienda.ciudad or "Sin ciudad",
                "dia": int(registro.dia),
                "dia_semana_anterior": _nombre_dia(anio - 1, mes, registro.dia),
                "dia_semana_actual": _nombre_dia(anio, mes, registro.dia),
                "venta": None,
                "venta_anterior": float(registro.venta or 0),
                "diferencia": None,
                "crecimiento": None,
                "unidades": None,
                "valor_unidad": None,
                "pendiente": True,
            })
        detalle_completo.sort(key=lambda item: (item["codigo"], item["dia"]))

    total_venta = sum(item["venta"] for item in por_tienda.values())
    total_unidades = sum(item["unidades"] for item in por_tienda.values())
    ranking = []

    for item in por_tienda.values():
        comparacion_completa = (
            item["dias"] > 0 and item["dias_comparables"] == item["dias"]
        )
        item["diferencia"] = (
            item["venta"] - item["venta_anterior"]
            if comparacion_completa else None
        )
        item["crecimiento"] = (
            item["diferencia"] / item["venta_anterior"] * 100
            if item["diferencia"] is not None and item["venta_anterior"] > 0
            else None
        )
        item["comparacion_completa"] = comparacion_completa
        item["valor_unidad"] = (
            item["venta"] / item["unidades"] if item["unidades"] > 0 else 0.0
        )
        item["promedio_dia"] = (
            item["venta"] / item["dias"] if item["dias"] > 0 else 0.0
        )
        item["participacion"] = (
            item["venta"] / total_venta * 100 if total_venta > 0 else 0.0
        )
        ranking.append(dict(item))

    ranking.sort(key=lambda item: item["venta"], reverse=True)
    for posicion, item in enumerate(ranking, start=1):
        item["posicion"] = posicion

    dias = [
        {
            "dia": dia,
            "venta": valores["venta"],
            "venta_anterior": (
                valores["venta_anterior"]
                if valores["registros"] == valores["registros_anterior"]
                else None
            ),
            "diferencia": (
                valores["venta"] - valores["venta_anterior"]
                if valores["registros"] == valores["registros_anterior"]
                else None
            ),
            "crecimiento": (
                (valores["venta"] - valores["venta_anterior"])
                / valores["venta_anterior"] * 100
                if valores["registros"] == valores["registros_anterior"]
                and valores["venta_anterior"] > 0
                else None
            ),
            "unidades": valores["unidades"],
            "valor_unidad": (
                valores["venta"] / valores["unidades"]
                if valores["unidades"] > 0 else 0.0
            ),
        }
        for dia, valores in sorted(por_dia.items())
    ]

    max_venta = max((item["venta"] for item in detalle), default=0.0)
    matriz = []
    dias_disponibles = sorted(por_dia.keys())
    detalle_por_tienda_dia = {
        (item["store_id"], item["dia"]): item for item in detalle
    }

    for tienda in ranking:
        celdas = []
        for dia in dias_disponibles:
            valor = detalle_por_tienda_dia.get((tienda["store_id"], dia))
            venta = valor["venta"] if valor else 0.0
            nivel = round((venta / max_venta) * 4) if max_venta > 0 else 0
            celdas.append({
                "dia": dia,
                "venta": venta,
                "unidades": valor["unidades"] if valor else 0,
                "nivel": max(0, min(4, int(nivel))),
            })
        matriz.append({
            "codigo": tienda["codigo"],
            "nombre": tienda["nombre"],
            "celdas": celdas,
        })

    return {
        "hay_datos": bool(registros),
        "anio_anterior": anio - 1,
        "total_venta": total_venta,
        "total_unidades": total_unidades,
        "valor_unidad": total_venta / total_unidades if total_unidades else 0.0,
        "tiendas": len(ranking),
        "dias": dias,
        "ranking": ranking,
        "detalle": detalle,
        "detalle_completo": detalle_completo,
        "dias_disponibles": dias_disponibles,
        "matriz": matriz,
    }
