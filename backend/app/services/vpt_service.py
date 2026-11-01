"""
VPT (valor por tiquete) y UPT de la tienda frente al año anterior,
y meta mínima de VPT por tienda.

- Meta mínima de VPT: app/data/metas_vpt.json (por número de tienda, en pesos),
  generado desde "META VPT X TIENDA.xlsx" (promedio acumulado del año).
- Año anterior (en este orden):
  1. Hoja CUMPL del mismo Excel de ventas importado para ese corte (columnas
     "TICKET $" y "TICKET UNID." del año anterior). Es el dato oficial del informe.
     El archivo se busca en uploads/ con el nombre guardado en Compliance.
  2. Mismos días del año pasado: venta año anterior ÷ facturas (conversión diaria)
     y unidades (ventas diarias por tienda) ÷ facturas.
  3. Desempeño de asesoras del año pasado.
Nunca rompe el dashboard: si algo falla, devuelve los valores en None.
"""
import json
import os
import re

from app.extensions import db
from app.models import AdvisorPerformance, Compliance, ConversionDiaria, DailyStoreSales, Store

_CACHE_CUMPL = {}  # (ruta, fecha de modificación) -> {número de tienda: datos}

ARCHIVO_METAS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "metas_vpt.json"
)


def _numero_tienda(codigo):
    """'S 04', 'S-04', 'S04' -> '4'."""
    coincidencia = re.match(r"\s*S\s*-?\s*(\d+)", str(codigo or ""), re.IGNORECASE)
    return str(int(coincidencia.group(1))) if coincidencia else None


def _metas_vpt():
    try:
        with open(ARCHIVO_METAS, encoding="utf-8") as archivo:
            return json.load(archivo).get("metas", {})
    except (OSError, ValueError):
        return {}


def _ultimo_por_dia(registros):
    """Para cada día, la versión del archivo con el corte más reciente."""
    resultado = {}
    for registro in registros:
        actual = resultado.get(int(registro.dia))
        if actual is None or int(registro.dia_corte or 0) > int(actual.dia_corte or 0):
            resultado[int(registro.dia)] = registro
    return list(resultado.values())


def _variacion(actual, anterior):
    if actual is None or not anterior:
        return None
    return (actual - anterior) / anterior


def _ruta_upload(nombre_archivo):
    if not nombre_archivo:
        return None
    nombre = os.path.basename(str(nombre_archivo))
    backend = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for carpeta in (os.path.join(os.getcwd(), "uploads"), os.path.join(backend, "uploads")):
        ruta = os.path.join(carpeta, nombre)
        if os.path.isfile(ruta):
            return ruta
    return None


def _leer_cumpl(ruta, anio):
    """Lee la hoja CUMPL (igual que el importador) y devuelve los datos del año anterior por tienda."""
    clave = (ruta, os.path.getmtime(ruta), int(anio))
    if clave in _CACHE_CUMPL:
        return _CACHE_CUMPL[clave]
    import pandas as pd
    df = pd.read_excel(ruta, sheet_name="CUMPL", header=2)
    df.columns = [str(c).strip() if not isinstance(c, int) else c for c in df.columns]
    ant = int(anio) - 1
    col_facturas, col_vpt, col_upt = f"{ant}.2", f"{ant}.4", f"{ant}.5"
    datos = {}
    if all(c in df.columns for c in (col_facturas, col_vpt, col_upt)):
        for _, fila in df.iterrows():
            numero = None
            for col in ("TIENDA", "Unnamed: 0"):
                if col in df.columns and not pd.isna(fila.get(col)):
                    numero = _numero_tienda(fila.get(col))
                    if numero:
                        break
            if not numero:
                continue
            def valor(col):
                v = fila.get(col)
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    return None
                return v if v == v and v > 0 else None  # sin NaN ni ceros
            datos[numero] = {"facturas": valor(col_facturas), "vpt": valor(col_vpt), "upt": valor(col_upt)}
    if len(_CACHE_CUMPL) > 20:
        _CACHE_CUMPL.clear()
    _CACHE_CUMPL[clave] = datos
    return datos


def _desde_excel(store_id, anio, mes, dia_corte, codigo):
    consulta = Compliance.query.filter(
        Compliance.store_id == store_id,
        Compliance.anio == anio,
        Compliance.mes == mes
    )
    if dia_corte:
        consulta = consulta.filter(Compliance.dia_corte == dia_corte)
    registro = consulta.order_by(Compliance.dia_corte.desc(), Compliance.id.desc()).first()
    ruta = _ruta_upload(registro.nombre_archivo if registro else None)
    numero = _numero_tienda(codigo)
    if not ruta or not numero:
        return None
    return _leer_cumpl(ruta, anio).get(numero)


def _anio_anterior(store_id, anio, mes, dia_corte, venta_anterior, codigo=None):
    """Devuelve (vpt_anterior, upt_anterior, fuente)."""
    anio_ant = int(anio) - 1

    # 0. Hoja CUMPL del Excel importado (dato oficial)
    try:
        fila = _desde_excel(store_id, anio, mes, dia_corte, codigo)
    except Exception:
        fila = None
    if fila and fila.get("vpt"):
        return fila["vpt"], fila.get("upt"), "excel"

    # 1. Conversión diaria (facturas) + ventas diarias por tienda (unidades)
    consulta = ConversionDiaria.query.filter(
        ConversionDiaria.store_id == store_id,
        ConversionDiaria.anio == anio_ant,
        ConversionDiaria.mes == mes
    )
    if dia_corte:
        consulta = consulta.filter(ConversionDiaria.dia <= dia_corte)
    facturas_ant = sum(int(r.facturas or 0) for r in _ultimo_por_dia(consulta.all()))

    if facturas_ant > 0 and venta_anterior > 0:
        consulta_u = DailyStoreSales.query.filter(
            DailyStoreSales.store_id == store_id,
            DailyStoreSales.anio == anio_ant,
            DailyStoreSales.mes == mes
        )
        if dia_corte:
            consulta_u = consulta_u.filter(DailyStoreSales.dia <= dia_corte)
        unidades_ant = sum(int(r.unidades or 0) for r in _ultimo_por_dia(consulta_u.all()))
        return (
            venta_anterior / facturas_ant,
            unidades_ant / facturas_ant if unidades_ant > 0 else None,
            "conversion"
        )

    # 2. Desempeño de asesoras del año pasado (el corte más cercano sin pasarse)
    consulta_a = AdvisorPerformance.query.filter(
        AdvisorPerformance.store_id == store_id,
        AdvisorPerformance.anio == anio_ant,
        AdvisorPerformance.mes == mes
    )
    cortes = sorted({int(r.dia_corte or 0) for r in consulta_a.with_entities(AdvisorPerformance.dia_corte).all()})
    if cortes:
        validos = [c for c in cortes if not dia_corte or c <= int(dia_corte)]
        corte = validos[-1] if validos else None
        if corte is not None:
            registros = consulta_a.filter(AdvisorPerformance.dia_corte == corte).all()
            venta = sum(float(r.venta or 0) for r in registros)
            facturas = sum(int(r.facturas or 0) for r in registros)
            unidades = sum(int(r.unidades or 0) for r in registros)
            if facturas > 0 and venta > 0:
                return venta / facturas, (unidades / facturas if unidades > 0 else None), "asesoras"

    return None, None, None


def indicadores_vpt(store_id, anio, mes, dia_corte, venta_anterior, vpt_actual, upt_actual):
    datos = {
        "meta_vpt": None,
        "cumplimiento_vpt": None,
        "vpt_anterior": None,
        "upt_anterior": None,
        "variacion_vpt": None,
        "variacion_upt": None,
        "fuente_anterior": None,
    }
    try:
        vpt_actual = float(vpt_actual or 0)
        upt_actual = float(upt_actual or 0)

        tienda = Store.query.get(store_id)
        numero = _numero_tienda(tienda.codigo if tienda else None)
        meta = _metas_vpt().get(numero) if numero else None
        if meta:
            datos["meta_vpt"] = float(meta)
            datos["cumplimiento_vpt"] = vpt_actual / float(meta) if vpt_actual > 0 else None

        if anio and mes:
            vpt_ant, upt_ant, fuente = _anio_anterior(
                store_id, anio, mes, dia_corte, float(venta_anterior or 0),
                tienda.codigo if tienda else None
            )
            datos.update({
                "vpt_anterior": vpt_ant,
                "upt_anterior": upt_ant,
                "variacion_vpt": _variacion(vpt_actual or None, vpt_ant),
                "variacion_upt": _variacion(upt_actual or None, upt_ant),
                "fuente_anterior": fuente,
            })
    except Exception:
        # Una consulta fallida deja la transacción abortada (PostgreSQL); se limpia
        # para que el resto del dashboard siga consultando normal.
        db.session.rollback()
    return datos
