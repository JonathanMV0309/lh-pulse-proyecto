"""Arma el histórico mensual limpio que usa el motor para entrenar.

``sales_history_lines`` guarda el acumulado a la fecha del último archivo
cargado para cada mes (los tableros lo necesitan así para comparar contra el
mismo día del año anterior). Eso deja, para el modelo, tres problemas:

1. Meses incompletos: un corte parcial sobrescribe el mes cerrado, tanto del
   año actual como del anterior.
2. Meses inflados o con columnas corridas en algunos archivos.
3. Años corridos: versiones anteriores del importador escribían siempre
   2025/2026, por lo que archivos de otro año quedaron etiquetados mal y
   aparecen ventas en meses que todavía no ocurren.

La solución no modifica la base de datos. Se toma el total cerrado por tienda
y mes de ``compliance`` (la fuente oficial del tablero) como verdad y del
histórico por línea solo la proporción entre líneas.
"""

import calendar

import numpy as np
import pandas as pd


# Tolerancias para meses sin total cerrado que lo verifique.
MIN_RATIO_PLAUSIBLE = 0.55
MAX_RATIO_PLAUSIBLE = 1.80


def _period_index(year, month):
    return int(year) * 12 + int(month) - 1


def _ensure_numeric(frame, columns):
    result = frame.copy()
    for column in columns:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def corregir_anios_futuros(sales, today_period, compliance=None):
    """Corre un año atrás los grupos tienda/mes que tienen ventas en el futuro.

    Un registro con fecha posterior al mes en curso es imposible; aparece
    cuando un archivo de un año se guardó con la etiqueta del año siguiente.
    El importador anterior siempre escribía la pareja (2025, 2026), así que
    todo el grupo tienda/mes queda corrido y se corrige completo.

    Para el mes en curso, un registro solo es legítimo si ``compliance`` ya
    tiene un corte de ese mes para la tienda; si no, viene de otro año.
    """
    if sales.empty:
        return sales.copy(), 0
    result = sales.copy()
    result["_p"] = [_period_index(y, m) for y, m in zip(result["anio"], result["mes"])]
    limit = _period_index(*today_period)
    current_with_cut = set()
    if compliance is not None and not compliance.empty:
        current = compliance[
            (compliance["anio"].astype(int) == int(today_period[0]))
            & (compliance["mes"].astype(int) == int(today_period[1]))
        ]
        current_with_cut = set(current["store_id"].astype(int))
    current_month = (result["_p"] == limit) & ~result["store_id"].astype(int).isin(current_with_cut)
    shifted_groups = 0
    for iteration in range(3):  # suficiente para cualquier corrimiento acumulado
        suspicious = result["_p"] > limit
        if iteration == 0:
            suspicious = suspicious | current_month
        future = result[suspicious][["store_id", "mes"]].drop_duplicates()
        if future.empty:
            break
        keys = set(map(tuple, future.to_numpy()))
        mask = [
            (int(store), int(month)) in keys
            for store, month in zip(result["store_id"], result["mes"])
        ]
        mask = np.asarray(mask, dtype=bool)
        result.loc[mask, "anio"] = result.loc[mask, "anio"].astype(int) - 1
        result.loc[mask, "_p"] = result.loc[mask, "_p"] - 12
        shifted_groups += len(keys)
    return result.drop(columns="_p"), shifted_groups


def totales_cerrados(compliance):
    """Total de venta cerrado por tienda y mes a partir de ``compliance``.

    - ``venta_actual`` de un corte de cierre es el mes completo de ese año.
    - ``venta_anterior`` de un corte de cierre es el mes completo del año
      anterior (sirve para meses sin archivo propio).
    Se prefiere ``venta_actual``.
    """
    columns = ["store_id", "anio", "mes", "venta_cerrada", "fuente_total"]
    if compliance is None or compliance.empty:
        return pd.DataFrame(columns=columns)
    frame = _ensure_numeric(compliance, ["venta_actual", "venta_anterior", "dia_corte"])
    days = [calendar.monthrange(int(y), int(m))[1] for y, m in zip(frame["anio"], frame["mes"])]
    closed = frame["es_cierre"].fillna(False).astype(bool) | (frame["dia_corte"].fillna(0) >= days)
    frame = frame[closed]

    current = frame[frame["venta_actual"] > 0][["store_id", "anio", "mes", "venta_actual"]]
    current = current.rename(columns={"venta_actual": "venta_cerrada"}).assign(
        fuente_total="cierre_actual", _orden=0
    )
    previous = frame[frame["venta_anterior"] > 0][["store_id", "anio", "mes", "venta_anterior"]]
    previous = previous.rename(columns={"venta_anterior": "venta_cerrada"}).assign(
        anio=lambda d: d["anio"].astype(int) - 1, fuente_total="cierre_anio_siguiente", _orden=1
    )
    totals = pd.concat([current, previous], ignore_index=True)
    if totals.empty:
        return pd.DataFrame(columns=columns)
    totals["anio"] = totals["anio"].astype(int)
    totals["mes"] = totals["mes"].astype(int)
    totals = totals.sort_values("_orden").drop_duplicates(["store_id", "anio", "mes"], keep="first")
    return totals[columns].reset_index(drop=True)


def _referencia_interanual(store_month, totals):
    """Valor esperado de cada tienda/mes según el mismo mes del otro año.

    Usa solo totales confiables (cerrados) y los ajusta con el crecimiento
    típico de la red para ese mes. Devuelve NaN si no hay contra qué comparar.
    """
    trusted = {}
    for row in totals.itertuples(index=False):
        trusted[(int(row.store_id), int(row.anio), int(row.mes))] = float(row.venta_cerrada)

    growth = {}
    for (store, year, month), value in trusted.items():
        previous = trusted.get((store, year - 1, month))
        if previous and previous > 0 and value > 0:
            growth.setdefault((year, month), []).append(value / previous)
    growth = {key: float(np.median(values)) for key, values in growth.items() if len(values) >= 5}

    expected = []
    for store, year, month in store_month[["store_id", "anio", "mes"]].astype(int).to_numpy():
        before = trusted.get((store, year - 1, month))
        after = trusted.get((store, year + 1, month))
        if before:
            expected.append(before * growth.get((year, month), 1.0))
        elif after:
            expected.append(after / growth.get((year + 1, month), 1.0))
        else:
            expected.append(np.nan)
    return np.asarray(expected, dtype=float)


def _reparar_mezcla(lines, store_month):
    """Reemplaza la mezcla de líneas de archivos con columnas corridas.

    En algunos archivos (mayo, junio y julio) las columnas por línea vienen
    corridas: el total no cuadra con el cierre y una línea aparece en 0% u
    otra se multiplica. Para esos meses se usa la mezcla habitual de la tienda
    (mediana de sus meses verificados), o la de la red si no tiene.
    """
    ratio = store_month["venta"] / store_month["venta_cerrada"]
    reliable_months = store_month[store_month["calidad"] == "verificado"][["store_id", "anio", "mes"]]
    reference_rows = lines.merge(reliable_months, on=["store_id", "anio", "mes"])
    if reference_rows.empty:
        return lines, 0
    store_ref = reference_rows.groupby(["store_id", "line_id"])["share"].median().unstack(fill_value=0.0)
    network_ref = reference_rows.groupby("line_id")["share"].median()
    store_ref = store_ref.div(store_ref.sum(axis=1), axis=0)
    network_ref = network_ref / network_ref.sum()

    current = lines.pivot_table(index=["store_id", "anio", "mes"], columns="line_id",
                                values="share", aggfunc="sum", fill_value=0.0)
    references = pd.DataFrame(
        [store_ref.loc[store] if store in store_ref.index else network_ref
         for store in current.index.get_level_values("store_id")],
        index=current.index,
    ).reindex(columns=current.columns, fill_value=0.0).fillna(0.0)
    distance = (current - references).abs().sum(axis=1)

    month_ratio = store_month.assign(ratio=ratio).set_index(["store_id", "anio", "mes"])["ratio"]
    off_total = (month_ratio.reindex(current.index) - 1).abs() > 0.03
    bad = (distance > 0.25) | off_total.fillna(False)
    bad_keys = set(current.index[bad.to_numpy()])
    if not bad_keys:
        return lines, 0

    keys = list(zip(lines["store_id"], lines["anio"], lines["mes"]))
    mask = np.array([key in bad_keys for key in keys])
    replacement = [
        float(references.loc[key].get(line_id, 0.0))
        for key, line_id in zip(keys, lines["line_id"])
    ]
    lines.loc[mask, "share"] = np.asarray(replacement)[mask]
    # Líneas que faltan en el archivo dañado pero existen en la mezcla habitual.
    extra = []
    present = set(zip(lines["store_id"], lines["anio"], lines["mes"], lines["line_id"]))
    sample = lines[mask].drop_duplicates(["store_id", "anio", "mes"]).set_index(["store_id", "anio", "mes"])
    for key in bad_keys:
        if key not in sample.index:
            continue
        base = sample.loc[key]
        for line_id, share in references.loc[key].items():
            if share > 0 and (key[0], key[1], key[2], line_id) not in present:
                row = base.to_dict()
                row.update({"store_id": key[0], "anio": key[1], "mes": key[2],
                            "line_id": line_id, "share": float(share), "venta": 0.0})
                extra.append(row)
    if extra:
        lines = pd.concat([lines, pd.DataFrame(extra)], ignore_index=True)
    return lines, len(bad_keys)


def armar_historia(sales, compliance, today_period, cutoff_period=None):
    """Devuelve el histórico tienda/línea/mes listo para entrenar y un reporte.

    ``sales``: columnas store_id, line_id, anio, mes, venta.
    ``compliance``: store_id, anio, mes, venta_actual, venta_anterior,
    dia_corte, es_cierre (solo filas activas).
    """
    report = {
        "grupos_anio_corrido": 0,
        "tienda_mes_verificados": 0,
        "tienda_mes_ajustados": 0,
        "tienda_mes_sin_verificar": 0,
        "tienda_mes_descartados": 0,
        "tienda_mes_solo_total": 0,
        "tienda_mes_mezcla_reparada": 0,
        "meses_descartados": [],
    }
    if sales.empty:
        return sales.copy(), report

    sales = _ensure_numeric(sales, ["venta"])
    sales["anio"] = sales["anio"].astype(int)
    sales["mes"] = sales["mes"].astype(int)
    sales = sales.groupby(["store_id", "line_id", "anio", "mes"], as_index=False)["venta"].sum()
    sales, shifted = corregir_anios_futuros(sales, today_period, compliance)
    report["grupos_anio_corrido"] = int(shifted)

    if cutoff_period is not None:
        limit = _period_index(*cutoff_period)
        periods = [_period_index(y, m) for y, m in zip(sales["anio"], sales["mes"])]
        sales = sales[np.asarray(periods) <= limit].copy()

    sales["venta"] = sales["venta"].clip(lower=0)
    store_month = sales.groupby(["store_id", "anio", "mes"], as_index=False)["venta"].sum()
    totals = totales_cerrados(compliance)
    store_month = store_month.merge(totals, on=["store_id", "anio", "mes"], how="left")

    ratio = store_month["venta"] / store_month["venta_cerrada"]
    has_total = store_month["venta_cerrada"].notna() & (store_month["venta_cerrada"] > 0)
    store_month["calidad"] = np.where(
        has_total & ratio.between(0.995, 1.005), "verificado",
        np.where(has_total, "ajustado", "sin_verificar"),
    )

    # Meses sin total cerrado: se aceptan solo si son coherentes con el mismo
    # mes de la tienda en el otro año (ya verificado).
    unverified = store_month["calidad"] == "sin_verificar"
    if unverified.any():
        expected = _referencia_interanual(store_month, totals)
        plausible_ratio = store_month["venta"].to_numpy(dtype=float) / expected
        bad = unverified.to_numpy() & np.isfinite(expected) & ~(
            (plausible_ratio >= MIN_RATIO_PLAUSIBLE) & (plausible_ratio <= MAX_RATIO_PLAUSIBLE)
        )
        store_month.loc[bad, "calidad"] = "descartado"

    counts = store_month["calidad"].value_counts()
    report["tienda_mes_verificados"] = int(counts.get("verificado", 0))
    report["tienda_mes_ajustados"] = int(counts.get("ajustado", 0))
    report["tienda_mes_sin_verificar"] = int(counts.get("sin_verificar", 0))
    report["tienda_mes_descartados"] = int(counts.get("descartado", 0))

    # Ajuste: total cerrado × proporción de cada línea en el archivo.
    lines = sales.merge(
        store_month[["store_id", "anio", "mes", "venta", "venta_cerrada", "calidad"]].rename(
            columns={"venta": "venta_tienda"}
        ),
        on=["store_id", "anio", "mes"], how="left",
    )
    lines = lines[lines["calidad"] != "descartado"].copy()
    lines["share"] = np.divide(
        lines["venta"], lines["venta_tienda"],
        out=np.zeros(len(lines)), where=lines["venta_tienda"] > 0,
    )
    lines, repaired = _reparar_mezcla(lines, store_month)
    report["tienda_mes_mezcla_reparada"] = int(repaired)
    # Total del mes (cerrado si existe, si no el del archivo) × proporción.
    adjust = lines["calidad"].isin(["verificado", "ajustado"])
    month_total = np.where(adjust, lines["venta_cerrada"], lines["venta_tienda"])
    lines["venta"] = month_total * lines["share"]

    # Totales cerrados de meses que no tienen líneas: se reparten con la
    # mezcla habitual (ya reparada) de la tienda.
    usual_mix = {}
    for store_id, group in lines.groupby("store_id"):
        mix = group.groupby("line_id")["share"].median()
        if mix.sum() > 0:
            usual_mix[int(store_id)] = mix / mix.sum()
    present = set(map(tuple, store_month[["store_id", "anio", "mes"]].astype(int).to_numpy()))
    extra_rows = []
    limit = _period_index(*(cutoff_period or today_period))
    for row in totals.itertuples(index=False):
        key = (int(row.store_id), int(row.anio), int(row.mes))
        if key in present or _period_index(row.anio, row.mes) > limit:
            continue
        mix = usual_mix.get(int(row.store_id))
        if mix is None:
            continue
        for line_id, share in mix.items():
            extra_rows.append({
                "store_id": key[0], "line_id": int(line_id), "anio": key[1], "mes": key[2],
                "venta": float(row.venta_cerrada) * float(share),
            })
    report["tienda_mes_solo_total"] = len({(r["store_id"], r["anio"], r["mes"]) for r in extra_rows})

    clean = lines[["store_id", "line_id", "anio", "mes", "venta"]]
    if extra_rows:
        clean = pd.concat([clean, pd.DataFrame(extra_rows)], ignore_index=True)
    clean = clean.groupby(["store_id", "line_id", "anio", "mes"], as_index=False)["venta"].sum()

    discarded = store_month[store_month["calidad"] == "descartado"]
    report["meses_descartados"] = sorted(
        f"{int(y)}-{int(m):02d}" for y, m in discarded[["anio", "mes"]].drop_duplicates().to_numpy()
    )
    return clean.sort_values(["anio", "mes", "store_id", "line_id"]).reset_index(drop=True), report


def cobertura_mes(clean, entities, period):
    """Cobertura de un mes frente a las combinaciones que suelen vender.

    Se esperan las combinaciones tienda/línea activas que vendieron en alguno
    de los 12 meses anteriores; una tienda que nunca vende una línea no cuenta
    como faltante.
    """
    valid = entities[["store_id", "line_id"]].drop_duplicates()
    selling = clean[clean["venta"] > 0].copy()
    if selling.empty:
        return 0.0, 0, 0
    selling["_p"] = [_period_index(y, m) for y, m in zip(selling["anio"], selling["mes"])]
    target = _period_index(*period)
    window = selling[(selling["_p"] < target) & (selling["_p"] >= target - 12)]
    expected = window[["store_id", "line_id"]].drop_duplicates().merge(valid)
    if expected.empty:
        expected = valid
    found = selling[selling["_p"] == target][["store_id", "line_id"]].drop_duplicates()
    found = found.merge(expected)
    return len(found) / len(expected), len(expected), len(found)


def ultimo_mes_completo(clean, entities, cutoff_period, min_coverage, max_lookback=3):
    """Último mes ≤ corte cuyo histórico limpio tiene cobertura suficiente."""
    if clean.empty:
        return None, (0.0, 0, 0)
    year, month = cutoff_period
    first = None
    for step in range(max_lookback):
        index = _period_index(year, month) - step
        period = (index // 12, index % 12 + 1)
        coverage = cobertura_mes(clean, entities, period)
        if first is None:
            first = coverage
        if coverage[0] >= min_coverage:
            return period, coverage
    return None, first
