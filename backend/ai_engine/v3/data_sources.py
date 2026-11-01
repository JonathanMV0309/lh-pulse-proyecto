"""Lecturas de solo consulta para el motor V3."""

from pathlib import Path

import pandas as pd
from sqlalchemy import text


def load_stores(engine):
    query = text("""
        SELECT s.id AS store_id, s.codigo, s.nombre AS tienda,
               COALESCE(NULLIF(TRIM(s.ciudad), ''), 'SIN CIUDAD') AS ciudad,
               COALESCE(NULLIF(TRIM(s.clima), ''), 'SIN CLIMA') AS clima,
               COALESCE(r.nombre, 'SIN REGIÓN') AS region
        FROM stores s
        LEFT JOIN regions r ON r.id = s.region_id
        WHERE UPPER(COALESCE(s.estado, 'ACTIVA')) = 'ACTIVA'
          AND UPPER(COALESCE(s.nombre, '')) <> 'TOTAL'
          AND UPPER(COALESCE(s.codigo, '')) <> 'TOTAL'
        ORDER BY s.codigo
    """)
    return pd.read_sql(query, engine)


def load_lines(engine, line_ids):
    query = text("""
        SELECT id AS line_id, nombre AS linea
        FROM lines
        WHERE id = ANY(:line_ids)
        ORDER BY id
    """)
    return pd.read_sql(query, engine, params={"line_ids": list(line_ids)})


def load_sales(engine, cutoff_period):
    query = text("""
        SELECT store_id, line_id, anio, mes,
               SUM(COALESCE(venta, 0))::double precision AS venta
        FROM sales_history_lines
        WHERE (anio * 100 + mes) <= :cutoff
        GROUP BY store_id, line_id, anio, mes
        ORDER BY anio, mes, store_id, line_id
    """)
    return pd.read_sql(query, engine, params={"cutoff": cutoff_period})


def load_actual_snapshot(engine, year, month):
    """Último corte real disponible del mes que se está pronosticando.

    ``compliance`` es la fuente oficial del tablero y, a diferencia del
    histórico mensual usado para entrenar, contiene el acumulado al día.
    """
    query = text("""
        WITH cortes AS (
            SELECT store_id,
                   COALESCE(venta_actual, 0)::double precision AS venta_actual,
                   COALESCE(trafico, 0)::double precision AS trafico_actual,
                   COALESCE(facturas, 0)::double precision AS facturas_actual,
                   dia_corte,
                   ROW_NUMBER() OVER (
                       PARTITION BY store_id
                       ORDER BY dia_corte DESC NULLS LAST, fecha_carga DESC, id DESC
                   ) AS posicion
            FROM compliance
            WHERE activo = TRUE AND anio = :year AND mes = :month
              AND dia_corte IS NOT NULL
        )
        SELECT store_id, venta_actual, trafico_actual, facturas_actual, dia_corte
        FROM cortes
        WHERE posicion = 1
        ORDER BY store_id
    """)
    return pd.read_sql(query, engine, params={"year": year, "month": month})


def load_actual_line_sales(engine, year, month):
    """Acumulado por línea del mes objetivo, usado solo para repartir el real."""
    query = text("""
        SELECT store_id, line_id,
               SUM(COALESCE(venta, 0))::double precision AS venta_actual_linea
        FROM sales_history_lines
        WHERE anio = :year AND mes = :month
        GROUP BY store_id, line_id
        ORDER BY store_id, line_id
    """)
    return pd.read_sql(query, engine, params={"year": year, "month": month})


def load_store_operations(engine, cutoff_period):
    """Tráfico oficial y facturas mensuales con respaldo de Compliance.

    El histórico horario de facturas termina antes que el tráfico en algunas
    instalaciones. En esos meses se utiliza el último corte activo de
    ``compliance`` para no interpretar datos ausentes como cero.
    """
    query = text("""
        WITH horario AS (
            SELECT store_id,
                   EXTRACT(YEAR FROM fecha)::integer AS anio,
                   EXTRACT(MONTH FROM fecha)::integer AS mes,
                   CAST(SUM(trafico) FILTER (WHERE trafico IS NOT NULL) AS double precision) AS trafico,
                   CAST(SUM(facturas) FILTER (WHERE facturas IS NOT NULL) AS double precision) AS facturas,
                   SUM(CASE WHEN sensor_error THEN 1 ELSE 0 END)::integer AS horas_error,
                   COUNT(*)::integer AS horas
            FROM trafico_horario
            WHERE (EXTRACT(YEAR FROM fecha)::integer * 100
                   + EXTRACT(MONTH FROM fecha)::integer) <= :cutoff
            GROUP BY store_id, EXTRACT(YEAR FROM fecha), EXTRACT(MONTH FROM fecha)
        ),
        compliance_ordenado AS (
            SELECT store_id, anio, mes,
                   trafico::double precision AS trafico,
                   facturas::double precision AS facturas,
                   ROW_NUMBER() OVER (
                       PARTITION BY store_id, anio, mes
                       ORDER BY es_cierre DESC, dia_corte DESC NULLS LAST,
                                fecha_carga DESC, id DESC
                   ) AS posicion
            FROM compliance
            WHERE activo = TRUE AND (anio * 100 + mes) <= :cutoff
        ),
        compliance_mes AS (
            SELECT store_id, anio, mes, trafico, facturas
            FROM compliance_ordenado
            WHERE posicion = 1
        )
        SELECT COALESCE(h.store_id, c.store_id) AS store_id,
               COALESCE(h.anio, c.anio) AS anio,
               COALESCE(h.mes, c.mes) AS mes,
               COALESCE(h.trafico, c.trafico) AS trafico,
               COALESCE(h.facturas, c.facturas) AS facturas,
               COALESCE(h.horas_error, 0)::integer AS horas_error,
               COALESCE(h.horas, 0)::integer AS horas
        FROM horario h
        FULL OUTER JOIN compliance_mes c
          ON c.store_id = h.store_id AND c.anio = h.anio AND c.mes = h.mes
        ORDER BY anio, mes, store_id
    """)
    return pd.read_sql(query, engine, params={"cutoff": cutoff_period})


def load_goals(engine, year, month):
    query = text("""
        SELECT store_id, line_id, SUM(COALESCE(meta, 0))::double precision AS meta
        FROM meta_lines
        WHERE anio = :year AND mes = :month
        GROUP BY store_id, line_id
    """)
    return pd.read_sql(query, engine, params={"year": year, "month": month})


def load_external_city_features(path=None):
    """Carga opcional de turismo, clima, eventos y promociones por ciudad/mes.

    El CSV es opcional y debe contener ciudad, anio y mes. Nunca se inventan
    valores externos: si no existen, se usan ceros y el modelo lo documenta.
    """
    if path is None:
        path = Path(__file__).resolve().parents[1] / "data" / "external" / "city_month_features.csv"
    path = Path(path)
    columns = [
        "ciudad", "anio", "mes", "tourism_index", "temperature_avg",
        "rain_mm", "event_index", "promotion_index",
    ]
    if not path.exists():
        return pd.DataFrame(columns=columns)
    frame = pd.read_csv(path)
    missing = {"ciudad", "anio", "mes"} - set(frame.columns)
    if missing:
        raise ValueError(f"Faltan columnas externas: {sorted(missing)}")
    for column in columns[3:]:
        if column not in frame:
            frame[column] = 0.0
    frame["ciudad"] = frame["ciudad"].fillna("SIN CIUDAD").astype(str).str.strip().str.upper()
    return frame[columns]


def load_compliance_totals(engine):
    """Totales de venta por tienda/mes de ``compliance`` (último corte activo).

    El motor usa los cortes de cierre como verdad del total mensual de cada
    tienda; ver ``historia.armar_historia``.
    """
    query = text("""
        WITH ordenado AS (
            SELECT store_id, anio, mes,
                   COALESCE(venta_actual, 0)::double precision AS venta_actual,
                   COALESCE(venta_anterior, 0)::double precision AS venta_anterior,
                   dia_corte, COALESCE(es_cierre, FALSE) AS es_cierre,
                   trafico::double precision AS trafico,
                   facturas::double precision AS facturas,
                   ROW_NUMBER() OVER (
                       PARTITION BY store_id, anio, mes
                       ORDER BY es_cierre DESC, dia_corte DESC NULLS LAST,
                                fecha_carga DESC, id DESC
                   ) AS posicion
            FROM compliance
            WHERE activo = TRUE
        )
        SELECT store_id, anio, mes, venta_actual, venta_anterior, dia_corte, es_cierre,
               trafico, facturas
        FROM ordenado
        WHERE posicion = 1
        ORDER BY anio, mes, store_id
    """)
    return pd.read_sql(query, engine)


def load_daily_sales(engine):
    """Ventas diarias por tienda para estimar la curva de avance del mes.

    La tabla puede no existir en instalaciones sin la migración de ventas
    diarias; en ese caso el nowcast usa ritmo lineal como antes.
    """
    query = text("""
        SELECT store_id, anio, mes, dia,
               COALESCE(venta, 0)::double precision AS venta,
               dia_corte, es_cierre
        FROM daily_store_sales
        WHERE activo = TRUE
    """)
    try:
        return pd.read_sql(query, engine)
    except Exception:
        return pd.DataFrame(columns=["store_id", "anio", "mes", "dia", "venta", "dia_corte", "es_cierre"])
