from app.utils.logs import log_debug
import os
import re
import pandas as pd
import unicodedata

from calendar import monthrange
from datetime import datetime
from flask import session
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db

from app.models import (
    Store,
    Compliance,
    ConversionDiaria,
    Advisor,
    AdvisorPerformance,
    ArchivoImportado,
    Line,
    MetaLine,
    SalesHistoryLine,
    DailySales,
    DailyStoreSales
)


# ==========================================================
# UTILIDADES
# ==========================================================

def numero(valor):
    if valor is None:
        return 0.0
    try:
        if pd.isna(valor):
            return 0.0
    except Exception:
        pass
    try:
        return float(valor)
    except (ValueError, TypeError):
        return 0.0


def entero(valor):
    if valor is None:
        return 0
    try:
        if pd.isna(valor):
            return 0
    except Exception:
        pass
    try:
        return int(float(valor))
    except (ValueError, TypeError):
        return 0


def normalizar_texto(valor):
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    texto = str(valor).strip().upper()

    # Reemplazo de mojibake
    replacements = {
        "Ã‘": "Ñ", "Ã©": "É", "Ã‰": "É",
        "Ã": "Í", "Â": "", "Â¿": "¿", "Â¡": "¡",
    }
    for mal, bien in replacements.items():
        texto = texto.replace(mal, bien)

    # Corregir ?? según letra anterior
    texto = re.sub(r'([A-Z])\?\?', lambda m: m.group(1) + ('Ñ' if m.group(1)=='N' else 'Í'), texto)

    # Eliminar ? restantes
    texto = texto.replace("?", "")

    # Quitar espacios dobles
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def normalizar_nombre_asesora(valor):
    """Limpia y normaliza nombres de asesoras para evitar duplicados."""
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    texto = str(valor).strip().upper()

    # Reemplazos específicos de mojibake común
    reemplazos = {
        "Ã‘": "Ñ",
        "Ã©": "É",
        "Ã‰": "É",
        "Ã": "Í",
        "Â": "",
        "Â¿": "¿",
        "Â¡": "¡",
        "PEÃ‘A": "PEÑA",
        "MUÃ‘OZ": "MUÑOZ",
    }
    for mal, bien in reemplazos.items():
        texto = texto.replace(mal, bien)

    # Reemplazar signos de interrogación por Ñ en apellidos comunes
    texto = re.sub(r"MU\?+OZ", "MUÑOZ", texto)
    texto = re.sub(r"PE\?+A", "PEÑA", texto)
    texto = re.sub(r"NU\?+EZ", "NUÑEZ", texto)

    # Normalizar Unicode y quitar tildes
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii")

    # Eliminar caracteres no deseados excepto letras, números y espacios
    texto = re.sub(r"[^A-Z0-9 ]", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


# ==========================================================
# BUSCAR TIENDA
# ==========================================================

def buscar_tienda(valor):
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except Exception:
        pass
    texto = normalizar_texto(valor)
    if not texto:
        return None
    tiendas = Store.query.all()
    for tienda in tiendas:
        if normalizar_texto(tienda.codigo) == texto:
            return tienda
    for tienda in tiendas:
        if normalizar_texto(tienda.nombre) == texto:
            return tienda
    match = re.match(r"^S\s*-?\s*(\d{1,3})", texto)
    if match:
        numero_tienda = match.group(1).zfill(2)
        for tienda in tiendas:
            codigo_bd = normalizar_texto(tienda.codigo)
            codigo_bd = re.sub(r"^S\s*-?\s*", "", codigo_bd).strip()
            if codigo_bd.isdigit() and codigo_bd.zfill(2) == numero_tienda:
                return tienda
    nombre_sin_codigo = re.sub(r"^S\s*-?\s*\d{1,3}\s*", "", texto).strip()
    if nombre_sin_codigo:
        for tienda in tiendas:
            nombre_bd_sin_codigo = re.sub(
                r"^S\s*-?\s*\d{1,3}\s*",
                "",
                normalizar_texto(tienda.nombre)
            ).strip()
            if nombre_bd_sin_codigo == nombre_sin_codigo:
                return tienda
    # Sin signos de puntuación: «TIENDA VIRTUAL.» es la misma «TIENDA VIRTUAL»
    limpio = _sin_signos(texto)
    if limpio:
        for tienda in tiendas:
            if _sin_signos(normalizar_texto(tienda.nombre)) == limpio:
                return tienda
    return None


def _sin_signos(texto):
    return " ".join(re.sub(r"[^A-Z0-9Ñ]+", " ", str(texto or "")).split())


def codigo_de_fila(texto):
    """Código S-xx de una fila de ventas por día: por el código al inicio o, si no lo trae
    (como «TIENDA VIRTUAL.»), por el nombre de la tienda."""
    coincidencia = re.match(r"^S\s*-?\s*(\d{1,3})\b", texto)
    if coincidencia:
        return f"S-{coincidencia.group(1).zfill(2)}"
    tienda = buscar_tienda(texto)
    if not tienda or not tienda.codigo or normalizar_texto(tienda.nombre) == "TOTAL" or normalizar_texto(tienda.codigo) == "TOTA":
        return None
    return tienda.codigo


# ==========================================================
# DETERMINAR CORTE DESDE EXCEL
# ==========================================================

def determinar_corte_excel(ruta):
    nombre_archivo = os.path.basename(ruta)
    nombre_mayuscula = normalizar_texto(nombre_archivo)
    es_cierre = "CIERRE" in nombre_mayuscula
    anio = 2026
    mes = 7
    dia_corte = 31
    meses_es = {
        "ENE": 1, "ENERO": 1,
        "FEB": 2, "FEBRERO": 2,
        "MAR": 3, "MARZO": 3,
        "ABR": 4, "ABRIL": 4,
        "MAY": 5, "MAYO": 5,
        "JUN": 6, "JUNIO": 6,
        "JUL": 7, "JULIO": 7,
        "AGO": 8, "AGOSTO": 8,
        "SEP": 9, "SEPT": 9, "SEPTIEMBRE": 9, "SET": 9, "SETIEMBRE": 9,
        "OCT": 10, "OCTUBRE": 10,
        "NOV": 11, "NOVIEMBRE": 11,
        "DIC": 12, "DICIEMBRE": 12
    }
    nombre_busqueda = nombre_mayuscula
    nombre_busqueda = (
        nombre_busqueda
        .replace("Á", "A").replace("É", "E").replace("Í", "I")
        .replace("Ó", "O").replace("Ú", "U")
    )
    patron_mes_anio = re.search(
        r"\b(ENE|ENERO|FEB|FEBRERO|MAR|MARZO|ABR|ABRIL|MAY|MAYO|JUN|JUNIO|JUL|JULIO|AGO|AGOSTO|SEP|SEPT|SEPTIEMBRE|SET|SETIEMBRE|OCT|OCTUBRE|NOV|NOVIEMBRE|DIC|DICIEMBRE)\s*[-/]?\s*(20\d{2})\b",
        nombre_busqueda,
        re.IGNORECASE
    )
    if patron_mes_anio:
        mes_str = patron_mes_anio.group(1).upper()
        anio = int(patron_mes_anio.group(2))
        mes = meses_es.get(mes_str, mes)
        texto_antes_mes = nombre_busqueda[:patron_mes_anio.start()]
        patron_rango = re.search(r"(\d{1,2})\s*[-–—]\s*(\d{1,2})", texto_antes_mes)
        if patron_rango:
            dia_corte = int(patron_rango.group(2))
        else:
            patron_dia = re.search(r"(\d{1,2})\s*$", texto_antes_mes)
            if patron_dia:
                dia_corte = int(patron_dia.group(1))
            else:
                patron_dia_fallback = re.search(r"(\d{1,2})\s*(?:[-–—])?\s*$", texto_antes_mes)
                if patron_dia_fallback:
                    dia_corte = int(patron_dia_fallback.group(1))
    else:
        try:
            with pd.ExcelFile(ruta) as xls:
                hojas = xls.sheet_names
            if "CONVERSIÓN_x_DIA" in hojas:
                df = pd.read_excel(ruta, sheet_name="CONVERSIÓN_x_DIA", header=None)
                fechas = []
                for col in range(5, df.shape[1], 3):
                    fecha = df.iloc[3, col]
                    if pd.isna(fecha):
                        continue
                    try:
                        fecha = pd.to_datetime(fecha)
                        fechas.append(fecha)
                    except Exception:
                        continue
                if fechas:
                    fechas.sort()
                    anio = fechas[0].year
                    mes = fechas[0].month
                    dia_corte = max(fecha.day for fecha in fechas)
        except Exception as e:
            print("Error al leer CONVERSIÓN_x_DIA:", e)
    if not anio:
        anio = 2026
    if not mes:
        mes = 7
    if not dia_corte:
        dia_corte = 31
    if dia_corte < 1:
        dia_corte = 1
    if dia_corte > 31:
        dia_corte = 31
    resultado = {
        "anio": anio,
        "mes": mes,
        "dia_corte": dia_corte,
        "es_cierre": es_cierre,
        "nombre_archivo": nombre_archivo
    }
    log_debug("=" * 60)
    log_debug("CORTE DETECTADO")
    log_debug("=" * 60)
    log_debug(f"Archivo: {nombre_archivo}")
    log_debug(f"Año: {anio}")
    log_debug(f"Mes: {mes}")
    log_debug(f"Día corte: {dia_corte}")
    log_debug(f"Cierre: {es_cierre}")
    log_debug("=" * 60)
    return resultado


# ==========================================================
# BUSCAR ARCHIVO YA IMPORTADO
# ==========================================================

def buscar_archivo_importado(nombre_archivo, anio, mes, dia_corte):
    return ArchivoImportado.query.filter_by(
        nombre_archivo=nombre_archivo,
        anio=anio,
        mes=mes,
        dia_corte=dia_corte
    ).first()


# ==========================================================
# REGISTRAR ARCHIVO IMPORTADO
# ==========================================================

def registrar_archivo_importado(ruta, corte_info):
    usuario_id = session.get("user_id") or 1
    archivo = ArchivoImportado(
        nombre_archivo=corte_info["nombre_archivo"],
        ruta=ruta,
        anio=corte_info["anio"],
        mes=corte_info["mes"],
        dia_corte=corte_info["dia_corte"],
        es_cierre=corte_info["es_cierre"],
        usuario_id=usuario_id,
        fecha_carga=datetime.utcnow(),
        fecha_modificacion=datetime.utcnow(),
        estado="ACTIVO"
    )
    db.session.add(archivo)
    return archivo


# ==========================================================
# COMPARACIÓN DE PERIODOS
# ==========================================================

def es_periodo_posterior(anio_nuevo, mes_nuevo, anio_activo, mes_activo):
    return (anio_nuevo, mes_nuevo) > (anio_activo, mes_activo)


def es_periodo_anterior(anio_nuevo, mes_nuevo, anio_activo, mes_activo):
    return (anio_nuevo, mes_nuevo) < (anio_activo, mes_activo)


# ==========================================================
# GUARDAR COMPLIANCE CON CONTROL DE CORTE
# ==========================================================

def guardar_compliance_con_corte(store_id, anio, mes, dia_corte, es_cierre, nombre_archivo, datos):
    activo = Compliance.query.filter_by(store_id=store_id, anio=anio, mes=mes, activo=True).first()
    if activo:
        if activo.anio == anio and activo.mes == mes and activo.dia_corte == dia_corte and not activo.es_cierre:
            if "dif_acum" in datos:
                activo.dif_acum = datos["dif_acum"]
                db.session.add(activo)
            return (True, "Actualizado dif_acum en corte existente", activo)
        if es_periodo_anterior(anio, mes, activo.anio, activo.mes):
            return (False, f"El período {anio}-{mes:02d} es anterior al activo {activo.anio}-{activo.mes:02d}", None)
        if activo.anio == anio and activo.mes == mes:
            if activo.es_cierre and not es_cierre:
                return (False, "No se puede reemplazar un cierre con archivo normal", None)
            if activo.es_cierre and es_cierre and activo.dia_corte == dia_corte:
                return (False, "Ya existe un cierre para este período", activo)
            if not es_cierre and not activo.es_cierre and activo.dia_corte == dia_corte:
                return (False, f"Ya existe un corte del día {dia_corte}", activo)
            if es_cierre or dia_corte > activo.dia_corte:
                activo.activo = False
                db.session.add(activo)
            else:
                return (False, f"El corte {dia_corte} no es más avanzado que el activo {activo.dia_corte}", None)
        else:
            activo.activo = False
            db.session.add(activo)

    nuevo = Compliance(
        store_id=store_id,
        anio=anio,
        mes=mes,
        dia_corte=dia_corte,
        es_cierre=es_cierre,
        activo=True,
        fecha_carga=datetime.utcnow(),
        nombre_archivo=nombre_archivo,
        **datos
    )
    db.session.add(nuevo)
    return (True, "Guardado correctamente", nuevo)


# ==========================================================
# GUARDAR CONVERSIÓN DIARIA CON CONTROL DE CORTE
# ==========================================================

def guardar_conversion_diaria_con_corte(store_id, anio, mes, dia_corte, es_cierre, nombre_archivo, registros_dia):
    anteriores = ConversionDiaria.query.filter_by(store_id=store_id, anio=anio, mes=mes, activo=True).all()
    if anteriores:
        primer_registro = anteriores[0]
        if es_periodo_anterior(anio, mes, primer_registro.anio, primer_registro.mes):
            return (False, "El período es anterior al activo", anteriores)
        if primer_registro.anio == anio and primer_registro.mes == mes:
            if primer_registro.es_cierre and not es_cierre:
                return (False, "No se puede reemplazar un cierre con archivo normal", anteriores)
            if primer_registro.es_cierre and es_cierre and primer_registro.dia_corte == dia_corte:
                return (False, "Ya existe conversión de este cierre", anteriores)
            if not es_cierre and not primer_registro.es_cierre and primer_registro.dia_corte == dia_corte:
                return (False, f"Ya existe conversión del corte {dia_corte}", anteriores)
            if not es_cierre and dia_corte <= primer_registro.dia_corte:
                return (False, "Corte no más avanzado", anteriores)
            for reg in anteriores:
                reg.activo = False
                db.session.add(reg)
        else:
            for reg in anteriores:
                reg.activo = False
                db.session.add(reg)
    nuevos = []
    for item in registros_dia:
        nuevo = ConversionDiaria(
            store_id=store_id,
            anio=anio,
            mes=mes,
            dia=item["dia"],
            trafico=item["trafico"],
            facturas=item["facturas"],
            conversion=item["conversion"],
            dia_corte=dia_corte,
            es_cierre=es_cierre,
            activo=True,
            fecha_carga=datetime.utcnow(),
            nombre_archivo=nombre_archivo
        )
        nuevos.append(nuevo)
    db.session.add_all(nuevos)
    return (True, f"Guardados {len(nuevos)} registros", nuevos)


# ==========================================================
# GUARDAR RENDIMIENTO DE ASESORA
# ==========================================================

def guardar_advisor_performance_con_corte(advisor_id, store_id, anio, mes, dia_corte, es_cierre, nombre_archivo, datos):
    activo = AdvisorPerformance.query.filter_by(advisor_id=advisor_id, store_id=store_id, anio=anio, mes=mes, activo=True).first()
    if activo:
        if es_periodo_anterior(anio, mes, activo.anio, activo.mes):
            return (False, "Período anterior al activo", None)
        if activo.anio == anio and activo.mes == mes:
            if activo.es_cierre and not es_cierre:
                return (False, "No se puede reemplazar un cierre con archivo normal", None)
            if activo.es_cierre and es_cierre and activo.dia_corte == dia_corte:
                return (False, "Ya existe rendimiento para este cierre", activo)
            if not es_cierre and not activo.es_cierre and activo.dia_corte == dia_corte:
                return (False, f"Ya existe rendimiento del corte {dia_corte}", activo)
            if not es_cierre and dia_corte <= activo.dia_corte:
                return (False, "Corte no más avanzado", None)
            activo.activo = False
            db.session.add(activo)
        else:
            activo.activo = False
            db.session.add(activo)
    nuevo = AdvisorPerformance(
        advisor_id=advisor_id,
        store_id=store_id,
        anio=anio,
        mes=mes,
        dia_corte=dia_corte,
        es_cierre=es_cierre,
        activo=True,
        fecha_carga=datetime.utcnow(),
        nombre_archivo=nombre_archivo,
        **datos
    )
    db.session.add(nuevo)
    return (True, "Guardado correctamente", nuevo)


# ==========================================================
# OBTENER O CREAR LÍNEA
# ==========================================================

def obtener_o_crear_linea(nombre_linea):
    line = Line.query.filter_by(nombre=nombre_linea).first()
    if not line:
        line = Line(nombre=nombre_linea)
        db.session.add(line)
        db.session.flush()
    return line


# ==========================================================
# IMPORTAR METAS POR LÍNEA
# ==========================================================

def importar_metas_linea(ruta, corte_info):
    log_debug("=" * 50)
    log_debug("IMPORTANDO METAS POR LÍNEA")
    log_debug("=" * 50)
    with pd.ExcelFile(ruta) as xls:
        hojas = xls.sheet_names
    if "METAS_x_LINEA" not in hojas:
        log_debug("Hoja 'METAS_x_LINEA' no encontrada. Se omite.")
        return 0
    df = pd.read_excel(ruta, sheet_name="METAS_x_LINEA", header=None)
    lineas_meta = {
        "FEMENINO": (6, 9),
        "PLUS-SIZE": (10, 13),
        "MASCULINO": (14, 17),
        "ACCESORIOS": (18, 21)
    }
    cargados = 0
    for _, fila in df.iterrows():
        if len(fila) < 1:
            continue
        codigo = fila.iloc[0]
        if pd.isna(codigo):
            continue
        codigo = str(codigo).strip()
        if not codigo:
            continue
        tienda = buscar_tienda(codigo)
        if not tienda:
            continue
        MetaLine.query.filter_by(store_id=tienda.id, anio=corte_info["anio"], mes=corte_info["mes"]).delete()
        for nombre_linea, (col_meta, col_cumpl) in lineas_meta.items():
            if col_meta >= len(fila) or col_cumpl >= len(fila):
                continue
            meta = numero(fila.iloc[col_meta])
            meta_prop = numero(fila.iloc[col_meta + 1])
            venta = numero(fila.iloc[col_meta + 2])
            cumpl = numero(fila.iloc[col_cumpl])
            if meta == 0 and venta == 0:
                continue
            line = obtener_o_crear_linea(nombre_linea)
            nuevo = MetaLine(
                store_id=tienda.id,
                line_id=line.id,
                anio=corte_info["anio"],
                mes=corte_info["mes"],
                meta=meta,
                meta_proporcional=meta_prop,
                venta=venta,
                cumplimiento_pct=cumpl
            )
            db.session.add(nuevo)
            cargados += 1
    log_debug(f"Metas por línea: {cargados} registros guardados")
    return cargados


# ==========================================================
# IMPORTAR HISTÓRICO DE VENTAS POR LÍNEA
# ==========================================================

def importar_historico_lineas(ruta, corte_info):
    log_debug("=" * 50)
    log_debug("IMPORTANDO HISTÓRICO DE VENTAS POR LÍNEA")
    log_debug("=" * 50)
    with pd.ExcelFile(ruta) as xls:
        hojas = xls.sheet_names
    if "VTA $" not in hojas:
        log_debug("Hoja 'VTA $' no encontrada. Se omite.")
        return 0
    df = pd.read_excel(ruta, sheet_name="VTA $", header=None)
    lineas_hist = {
        "FEMENINO": (6, 7),
        "PLUS-SIZE": (10, 11),
        "MASCULINO": (14, 15),
        "ACCESORIOS": (18, 19),
        "INTIMA": (22, 23),
        "OTROS": (26, 27)
    }
    # La hoja trae el año anterior y el año del archivo. Antes se escribían
    # siempre 2025 y 2026, y un archivo de otro año quedaba con el año corrido.
    anio_actual = int(corte_info["anio"])
    anio_anterior = anio_actual - 1
    cargados = 0
    omitidas = 0
    for _, fila in df.iterrows():
        if len(fila) < 1:
            continue
        codigo = fila.iloc[0]
        if pd.isna(codigo):
            continue
        codigo = str(codigo).strip()
        if not codigo:
            continue
        tienda = buscar_tienda(codigo)
        if not tienda:
            continue
        if not _historico_puede_reemplazarse(tienda.id, corte_info):
            omitidas += 1
            continue
        SalesHistoryLine.query.filter(
            SalesHistoryLine.store_id == tienda.id,
            SalesHistoryLine.mes == corte_info["mes"],
            SalesHistoryLine.anio.in_([anio_anterior, anio_actual])
        ).delete()
        for nombre_linea, (col_anterior, col_actual) in lineas_hist.items():
            if col_anterior >= len(fila) or col_actual >= len(fila):
                continue
            venta_anterior = numero(fila.iloc[col_anterior])
            venta_actual = numero(fila.iloc[col_actual])
            if venta_anterior == 0 and venta_actual == 0:
                continue
            line = obtener_o_crear_linea(nombre_linea)
            if venta_anterior > 0:
                db.session.add(SalesHistoryLine(store_id=tienda.id, line_id=line.id, anio=anio_anterior, mes=corte_info["mes"], venta=venta_anterior))
                cargados += 1
            if venta_actual > 0:
                db.session.add(SalesHistoryLine(store_id=tienda.id, line_id=line.id, anio=anio_actual, mes=corte_info["mes"], venta=venta_actual))
                cargados += 1
    if omitidas:
        log_debug(
            f"Histórico de ventas por línea: {omitidas} tiendas conservan un corte más "
            "avanzado y no se reemplazaron"
        )
    log_debug(f"Histórico de ventas por línea: {cargados} registros guardados")
    return cargados


def _historico_puede_reemplazarse(store_id, corte_info):
    """Evita que un archivo más viejo pise un corte más avanzado del mismo mes.

    Sigue la misma regla que ``guardar_compliance_con_corte``: un cierre no se
    reemplaza con un parcial y un parcial no se reemplaza con uno anterior.
    """
    activo = Compliance.query.filter_by(
        store_id=store_id,
        anio=corte_info["anio"],
        mes=corte_info["mes"],
        activo=True,
    ).first()
    if not activo:
        return True
    if activo.nombre_archivo == corte_info["nombre_archivo"]:
        return True
    nuevo_cierre = bool(corte_info["es_cierre"])
    if activo.es_cierre and not nuevo_cierre:
        return False
    if not activo.es_cierre and not nuevo_cierre and (activo.dia_corte or 0) > corte_info["dia_corte"]:
        return False
    return True


# ==========================================================
# IMPORTAR CUMPLIMIENTO (AHORA LEE DIF. ACUM. DESDE CUMPL)
# ==========================================================

def dias_cerrada_por_tienda(df, corte_info):
    """Días que cada tienda estuvo sin vender este mes (remodelación o apertura), según la hoja CUMPL.

    La hoja calcula la cuota proporcional de casi todas las tiendas con el mismo número de días; a una
    tienda que estuvo cerrada le cuenta solo los días que vendió. La diferencia son sus días cerrada."""
    from collections import Counter
    dias_mes = monthrange(int(corte_info["anio"]), int(corte_info["mes"]))[1]
    dias = {}
    for _, fila in df.iterrows():
        codigo = fila.get("TIENDA")
        prop, total = numero(fila.get("CUOTA \nPROPORC")), numero(fila.get("CUOTA TOT"))
        if pd.isna(codigo) or not str(codigo).strip() or prop <= 0 or total <= 0:
            continue
        dias[str(codigo).strip()] = round(prop / total * dias_mes)
    if len(dias) < 3:
        return {}
    comun = Counter(dias.values()).most_common(1)[0][0]
    return {codigo: comun - d for codigo, d in dias.items() if 0 < comun - d < dias_mes}


def cuota_al_corte(datos, corte_info, dias_cerrada=0):
    """Ajusta la cuota al corte al día de corte del archivo.

    Cuota al corte = cuota total × día de corte / días del mes (en el cierre, la cuota total).
    La hoja CUMPL la calcula con una celda de día que a veces no se actualiza; aquí se corrige solo
    esa diferencia de días: el cumplimiento y la venta promedio por día cambian en la misma
    proporción que la cuota (así se respeta cómo calcula el Excel cada tienda).
    Si la tienda estuvo cerrada parte del mes (dias_cerrada), su cuota total y su cuota al corte
    cuentan solo los días que vendió."""
    dias_mes = monthrange(int(corte_info["anio"]), int(corte_info["mes"]))[1]
    corte = max(1, min(int(corte_info["dia_corte"] or dias_mes), dias_mes))
    if corte_info.get("es_cierre"):
        corte = dias_mes
    venta, cuota_total = float(datos.get("venta_actual") or 0), float(datos.get("cuota_total") or 0)
    cuota_excel = float(datos.get("cuota_proporcional") or 0)
    if cuota_total <= 0:
        return {}
    if dias_cerrada:
        abierta = max(corte - dias_cerrada, 0)     # antes de reabrir no hay cuota al corte
        total = cuota_total * (dias_mes - dias_cerrada) / dias_mes
        cuota = cuota_total * abierta / dias_mes
        return {"cuota_total": total, "cuota_proporcional": cuota, "cumplimiento_pct": venta / cuota if cuota else 0.0,
                "venta_promedio_dia": venta / abierta if abierta else 0.0, "falta_para_cuota": total - venta}
    cuota = cuota_total * corte / dias_mes
    if cuota_excel > 0:
        factor = cuota_excel / cuota
        return {"cuota_proporcional": cuota,
                "cumplimiento_pct": float(datos.get("cumplimiento_pct") or 0) * factor,
                "venta_promedio_dia": float(datos.get("venta_promedio_dia") or 0) * factor}
    return {"cuota_proporcional": cuota, "cumplimiento_pct": venta / cuota, "venta_promedio_dia": venta / corte}


def importar_cumplimiento(ruta, corte_info):
    log_debug("=" * 50)
    log_debug("IMPORTANDO CUMPLIMIENTO")
    log_debug("=" * 50)

    with pd.ExcelFile(ruta) as xls:
        hojas = xls.sheet_names

    if "CUMPL" not in hojas:
        log_debug("Hoja 'CUMPL' no encontrada. Se omite.")
        return 0

    df = pd.read_excel(ruta, sheet_name="CUMPL", header=2)
    df.columns = [str(col).strip() if not isinstance(col, int) else col for col in df.columns]

    col_dif = None
    for col in df.columns:
        col_norm = ''.join(e for e in str(col).upper() if e.isalnum())
        if "DIF" in col_norm and "ACUM" in col_norm:
            col_dif = col
            break

    if col_dif is None:
        log_debug("No se encontró columna 'DIF. ACUM.' en CUMPL")
    else:
        log_debug(f"Columna DIF. ACUM. encontrada: {col_dif}")

    cargados = 0
    rechazados = 0
    errores = []
    # Tiendas que estuvieron cerradas parte del mes (remodelación): se miden solo con los días que vendieron
    cerradas = dias_cerrada_por_tienda(df, corte_info)
    from app.services import cierre_tienda_service as cierre_tienda
    con_cierre = set()
    for codigo_cerrada, dias in cerradas.items():
        log_debug(f"{codigo_cerrada}: {dias} días sin vender este mes; cuota ajustada a los días abiertos")

    for _, fila in df.iterrows():
        codigo = fila.get("TIENDA")
        if pd.isna(codigo):
            continue
        codigo = str(codigo).strip()
        if not codigo:
            continue
        tienda = buscar_tienda(codigo)
        if not tienda:
            continue

        dif_acum = 0.0
        if col_dif is not None:
            dif_acum = numero(fila.get(col_dif))

        datos = {
            "venta_actual": numero(fila.get(2026)),
            "venta_anterior": numero(fila.get(2025)),
            "incremento": numero(fila.get("INC")),
            "cuota_proporcional": numero(fila.get("CUOTA \nPROPORC")),
            "cuota_total": numero(fila.get("CUOTA TOT")),
            "cumplimiento_pct": numero(fila.get("CUMPLI\npropor")),
            "falta_para_cuota": numero(fila.get("FALTA\nPARA CUOTA")),
            "venta_promedio_dia": numero(fila.get("VTA PROM DIA")),
            "trafico": entero(fila.get("2026.1")),
            "facturas": entero(fila.get("2026.2")),
            "conversion": numero(fila.get("2026.3")),
            "ticket_promedio": numero(fila.get("2026.4")),
            "dif_acum": dif_acum
        }
        # La cuota al corte la calcula la página con el día del archivo (no la celda de día de la hoja CUMPL)
        # Si la tienda tiene «Cierre de tienda» en Novedades, manda la novedad (se aplica después de guardar)
        cierre_novedad = cierre_tienda.dias_cerrados(tienda.id, int(corte_info["anio"]), int(corte_info["mes"]))
        dias_excel = 0 if cierre_novedad else cerradas.get(codigo, 0)
        sin_cierre = dict(datos, **cuota_al_corte(datos, corte_info, 0))   # valores del mes completo (originales)
        datos.update(cuota_al_corte(datos, corte_info, dias_excel))

        exito, mensaje, registro = guardar_compliance_con_corte(
            store_id=tienda.id,
            anio=corte_info["anio"],
            mes=corte_info["mes"],
            dia_corte=corte_info["dia_corte"],
            es_cierre=corte_info["es_cierre"],
            nombre_archivo=corte_info["nombre_archivo"],
            datos=datos
        )
        if exito:
            cargados += 1
            if cierre_novedad:
                con_cierre.add(tienda.id)
            elif dias_excel and registro is not None:
                # Ajustada por lo que trae el Excel: se guarda la cuota del mes completo por si luego
                # registran el cierre en Novedades (así no se descuenta dos veces)
                cierre_tienda.guardar_original(registro, sin_cierre, dias_excel)
        else:
            rechazados += 1
            errores.append(f"{codigo}: {mensaje}")

    for store_id in con_cierre:
        cierre_tienda.reajustar(store_id, int(corte_info["anio"]), int(corte_info["mes"]), commit=False)
        log_debug(f"Tienda {store_id}: cuota ajustada por «Cierre de tienda» en Novedades")

    log_debug(f"Compliance: {cargados} guardados, {rechazados} rechazados")
    if errores:
        log_debug("Errores:")
        for error in errores:
            log_debug(f" - {error}")
    return cargados


# ==========================================================
# IMPORTAR CONVERSIÓN DIARIA
# ==========================================================

def importar_conversion_diaria(ruta, corte_info):
    log_debug("=" * 50)
    log_debug("IMPORTANDO CONVERSIÓN DIARIA")
    log_debug("=" * 50)
    with pd.ExcelFile(ruta) as xls:
        hojas = xls.sheet_names
    if "CONVERSIÓN_x_DIA" not in hojas:
        log_debug("Hoja 'CONVERSIÓN_x_DIA' no encontrada. Se omite.")
        return 0
    df = pd.read_excel(ruta, sheet_name="CONVERSIÓN_x_DIA", header=None)
    tiendas = {}
    for tienda in Store.query.all():
        if tienda.codigo:
            tiendas[normalizar_texto(tienda.codigo)] = tienda
    registros_por_tienda = {}
    anio = corte_info["anio"]
    mes = corte_info["mes"]
    for col in range(5, df.shape[1], 3):
        fecha = df.iloc[3, col]
        if pd.isna(fecha):
            continue
        # El número de día de la fila 3 (1, 2, 3...) manda; la fecha de la fila 4
        # puede venir desactualizada si la plantilla se copió de otro mes.
        try:
            dia = int(float(df.iloc[2, col]))
        except (ValueError, TypeError):
            dia = None
        try:
            fecha_dt = pd.to_datetime(fecha)
        except Exception:
            fecha_dt = None
        fecha_en_periodo = (
            fecha_dt is not None
            and fecha_dt.year == anio
            and fecha_dt.month == mes
        )
        if dia is None:
            dia = fecha_dt.day if fecha_en_periodo else ((col - 5) // 3) + 1
        elif fecha_dt is not None and (not fecha_en_periodo or fecha_dt.day != dia):
            log_debug(
                f"[ADVERTENCIA] CONVERSIÓN_x_DIA columna {col}: fecha {fecha_dt.date()} "
                f"no corresponde al día {dia} de {anio}-{mes:02d}; se usa el día {dia}"
            )
        if dia < 1 or dia > corte_info["dia_corte"]:
            continue
        for fila in range(5, df.shape[0]):
            codigo = df.iloc[fila, 1]
            if pd.isna(codigo):
                continue
            codigo = str(codigo).strip()
            if not codigo:
                continue
            tienda = tiendas.get(normalizar_texto(codigo))
            if not tienda:
                tienda = buscar_tienda(codigo)
            if not tienda:
                continue
            trafico = df.iloc[fila, col]
            facturas = df.iloc[fila, col + 1]
            conversion = df.iloc[fila, col + 2]
            if pd.isna(trafico) and pd.isna(facturas) and pd.isna(conversion):
                continue
            trafico = entero(trafico)
            facturas = entero(facturas)
            conversion = numero(conversion)
            key = (tienda.id, anio, mes)
            if key not in registros_por_tienda:
                registros_por_tienda[key] = []
            registros_por_tienda[key].append({
                "dia": dia,
                "trafico": trafico,
                "facturas": facturas,
                "conversion": conversion
            })
    total_guardados = 0
    for (store_id, anio, mes), registros in registros_por_tienda.items():
        exito, mensaje, nuevos = guardar_conversion_diaria_con_corte(
            store_id=store_id,
            anio=anio,
            mes=mes,
            dia_corte=corte_info["dia_corte"],
            es_cierre=corte_info["es_cierre"],
            nombre_archivo=corte_info["nombre_archivo"],
            registros_dia=registros
        )
        if exito:
            total_guardados += len(nuevos)
        else:
            log_debug(f"Conversión tienda {store_id}: {mensaje}")
    log_debug(f"Conversión diaria: {total_guardados} registros guardados")
    return total_guardados


# ==========================================================
# IMPORTAR ASESORAS
# ==========================================================

def importar_asesoras(ruta, corte_info):
    log_debug("=" * 50)
    log_debug("IMPORTANDO ASESORAS Y RENDIMIENTO")
    log_debug("=" * 50)
    with pd.ExcelFile(ruta) as xls:
        hojas = xls.sheet_names
    if "UPT_VPT_ASESOR" not in hojas:
        log_debug("Hoja 'UPT_VPT_ASESOR' no encontrada. Se omite.")
        return 0
    df = pd.read_excel(ruta, sheet_name="UPT_VPT_ASESOR", header=2)
    df.columns = df.columns.astype(str).str.strip()
    cargados = 0
    rechazados = 0
    errores = []
    for _, fila in df.iterrows():
        nombre = fila.get("NOMBRE_ASESOR")
        tienda_nombre = fila.get("TIENDA")
        if pd.isna(nombre) or pd.isna(tienda_nombre):
            continue
        nombre = str(nombre).strip()
        tienda_nombre = str(tienda_nombre).strip()
        if not nombre or not tienda_nombre:
            continue
        if nombre.lower() in ["(en blanco)", "nan", "none"]:
            continue
        if tienda_nombre.lower() in ["(en blanco)", "nan", "none"]:
            continue
        if nombre.lower().startswith("total"):
            continue
        tienda = buscar_tienda(tienda_nombre)
        if not tienda:
            continue

        nombre_normalizado = normalizar_nombre_asesora(nombre)

        asesora = None
        for a in Advisor.query.filter_by(store_id=tienda.id).all():
            if normalizar_nombre_asesora(a.nombre) == nombre_normalizado:
                asesora = a
                break

        if not asesora:
            asesora = Advisor(nombre=nombre, store_id=tienda.id, es_generico=False)
            db.session.add(asesora)
            db.session.flush()
        else:
            if asesora.nombre != nombre:
                asesora.nombre = nombre
                db.session.add(asesora)

        datos_performance = {
            "venta": numero(fila.get("VAL_FAC_2026")),
            "unidades": numero(fila.get("UNID_FAC_2026")),
            "facturas": numero(fila.get("CANT_FACT_2026")),
            "ticket_promedio": numero(fila.get("TICKET $ 2026")),
            "upt": numero(fila.get("TICKET UNID. 2026"))
        }
        exito, mensaje, registro = guardar_advisor_performance_con_corte(
            advisor_id=asesora.id,
            store_id=tienda.id,
            anio=corte_info["anio"],
            mes=corte_info["mes"],
            dia_corte=corte_info["dia_corte"],
            es_cierre=corte_info["es_cierre"],
            nombre_archivo=corte_info["nombre_archivo"],
            datos=datos_performance
        )
        if exito:
            cargados += 1
        else:
            rechazados += 1
            errores.append(f"{nombre} ({tienda.codigo}): {mensaje}")
    log_debug(f"Asesoras: {cargados} guardados, {rechazados} rechazados")
    if errores:
        log_debug("Errores:")
        for error in errores:
            log_debug(f" - {error}")
    return cargados


# ==========================================================
# NUEVO: GUARDAR DAILY SALES (VENTAS GLOBALES POR DÍA)
# ==========================================================
def guardar_daily_sales_con_corte(anio, mes, dia_corte, es_cierre, nombre_archivo, registros_dia):
    # Reimportar el mismo corte lo reemplaza, pero conserva los demás cortes
    # para que el filtro histórico siga funcionando.
    DailySales.query.filter_by(
        store_id=None,
        anio=anio,
        mes=mes,
        dia_corte=dia_corte,
    ).delete(synchronize_session=False)
    db.session.flush()

    nuevos = []
    for item in registros_dia:
        nuevo = DailySales(
            store_id=None,
            anio=anio,
            mes=mes,
            dia=item["dia"],
            venta_2025=item["venta_2025"],
            venta_2026=item["venta_2026"],
            incremento_pct=item["incremento_pct"],
            diferencia=item["diferencia"],
            dia_semana_2025=item.get("dia_semana_2025"),
            dia_semana_2026=item.get("dia_semana_2026"),
            dia_corte=dia_corte,
            es_cierre=es_cierre,
            activo=True,
            fecha_carga=datetime.utcnow(),
            nombre_archivo=nombre_archivo
        )
        nuevos.append(nuevo)
    db.session.add_all(nuevos)
    return (True, f"Guardados {len(nuevos)} registros", nuevos)


# ==========================================================
# NUEVO: IMPORTAR X DIA (GLOBAL)
# ==========================================================

def importar_xdia(ruta, corte_info):
    log_debug("=" * 50)
    log_debug("IMPORTANDO X DIA")
    log_debug("=" * 50)

    with pd.ExcelFile(ruta) as xls:
        hojas = xls.sheet_names

    hoja_xdia = None
    for hoja in hojas:
        hoja_norm = normalizar_texto(hoja).replace(" ", "").upper()
        if (
            hoja_norm.startswith("X")
            and "DIA" in hoja_norm
            and "TIENDA" not in hoja_norm
        ):
            hoja_xdia = hoja
            break

    if not hoja_xdia:
        log_debug("Hoja 'X DIA' no encontrada. Se omite.")
        return 0

    df = pd.read_excel(ruta, sheet_name=hoja_xdia, header=None)

    registros_dia = []

    # Recorrer desde la fila 12 (índice 11) hasta el final
    for idx in range(11, len(df)):
        fila = df.iloc[idx]

        # Día en columna A
        dia_val = fila[0]
        if pd.isna(dia_val):
            continue

        # Si es fila de totales, la omitimos
        if "TOT" in str(dia_val).upper() or "TOTAL" in str(dia_val).upper():
            continue

        dia = entero(dia_val)
        if dia <= 0:
            continue

        # Ventas por posición de columna
        venta_2025 = numero(fila[1])
        venta_2026 = numero(fila[2])
        diferencia = numero(fila[3])

        # Calcular incremento
        if venta_2025 > 0:
            incremento_pct = (diferencia / venta_2025) * 100
        else:
            incremento_pct = 0.0

        # Fechas (columnas E y F)
        fecha_2025 = fila[4]
        fecha_2026 = fila[5]

        dia_sem_2025 = ""
        dia_sem_2026 = ""
        if not pd.isna(fecha_2025):
            try:
                dia_sem_2025 = pd.to_datetime(fecha_2025).strftime("%A").upper()
            except Exception:
                pass
        if not pd.isna(fecha_2026):
            try:
                dia_sem_2026 = pd.to_datetime(fecha_2026).strftime("%A").upper()
            except Exception:
                pass

        registros_dia.append({
            "dia": dia,
            "venta_2025": venta_2025,
            "venta_2026": venta_2026,
            "incremento_pct": incremento_pct,
            "diferencia": diferencia,
            "dia_semana_2025": dia_sem_2025,
            "dia_semana_2026": dia_sem_2026,
        })

    if not registros_dia:
        log_debug("No se encontraron filas de datos.")
        return 0

    # Guardar con control de corte
    exito, mensaje, nuevos = guardar_daily_sales_con_corte(
        anio=corte_info["anio"],
        mes=corte_info["mes"],
        dia_corte=corte_info["dia_corte"],
        es_cierre=corte_info["es_cierre"],
        nombre_archivo=corte_info["nombre_archivo"],
        registros_dia=registros_dia
    )

    if exito:
        log_debug(f"X DIA: {len(nuevos)} registros guardados")
        return len(nuevos)
    else:
        log_debug(f"Error en X DIA: {mensaje}")
        return 0


# ==========================================================
# VENTAS Y UNIDADES DIARIAS POR TIENDA
# Hoja: X DIA X TIENDA
# ==========================================================

def extraer_xdia_tienda(ruta):
    """Extrae la matriz de ventas/unidades sin tocar la base de datos."""

    with pd.ExcelFile(ruta) as xls:
        hoja = next(
            (
                nombre
                for nombre in xls.sheet_names
                if "XDIA" in normalizar_texto(nombre).replace(" ", "")
                and "TIENDA" in normalizar_texto(nombre).replace(" ", "")
            ),
            None,
        )

    if not hoja:
        return [], None

    df = pd.read_excel(ruta, sheet_name=hoja, header=None)
    fila_encabezado = None

    for indice in range(min(len(df), 20)):
        primera = normalizar_texto(df.iloc[indice, 0])
        fila_texto = " ".join(
            normalizar_texto(valor) for valor in df.iloc[indice].tolist()
        )
        if "TIENDA" in primera and "UNID" in fila_texto:
            fila_encabezado = indice
            break

    if fila_encabezado is None or fila_encabezado == 0:
        return [], hoja

    fila_fechas = fila_encabezado - 1
    pares_fecha = []

    for columna in range(1, max(df.shape[1] - 1, 1)):
        encabezado_venta = normalizar_texto(df.iloc[fila_encabezado, columna])
        encabezado_unidades = normalizar_texto(
            df.iloc[fila_encabezado, columna + 1]
        )

        if encabezado_venta not in {"$", "VENTA", "VENTAS"}:
            continue
        if "UNID" not in encabezado_unidades:
            continue

        fecha_valor = df.iloc[fila_fechas, columna]
        try:
            fecha = pd.to_datetime(fecha_valor, errors="raise")
        except Exception:
            continue

        pares_fecha.append((columna, columna + 1, fecha))

    registros = []
    filas_omitidas = {"BOGOTA", "FUERA BTA", "FUERA BOGOTA"}

    for indice in range(fila_encabezado + 1, len(df)):
        nombre_tienda = normalizar_texto(df.iloc[indice, 0])
        if not nombre_tienda:
            continue
        if nombre_tienda in filas_omitidas or "TOTAL" in nombre_tienda:
            continue

        codigo = codigo_de_fila(nombre_tienda)
        if not codigo:
            continue

        for columna_venta, columna_unidades, fecha in pares_fecha:
            valor_venta = df.iloc[indice, columna_venta]
            valor_unidades = df.iloc[indice, columna_unidades]

            if pd.isna(valor_venta) and pd.isna(valor_unidades):
                continue

            registros.append({
                "codigo": codigo,
                "nombre_origen": nombre_tienda,
                "anio": int(fecha.year),
                "mes": int(fecha.month),
                "dia": int(fecha.day),
                "venta": numero(valor_venta),
                "unidades": entero(valor_unidades),
            })

    return registros, hoja


def importar_xdia_tienda(ruta, corte_info):
    registros, hoja = extraer_xdia_tienda(ruta)

    if not hoja:
        log_debug("Hoja 'X DIA X TIENDA' no encontrada. Se omite.")
        return 0

    if not registros:
        log_debug("X DIA X TIENDA: no se encontraron datos válidos.")
        return 0

    # Plantilla copiada de otro mes: si la primera fecha no cae en el período
    # del archivo, los días se ubican en ese período según su orden.
    periodo = (corte_info["anio"], corte_info["mes"])
    primera = min(
        datetime(item["anio"], item["mes"], item["dia"]) for item in registros
    )
    if (primera.year, primera.month) != periodo:
        log_debug(
            f"[ADVERTENCIA] X DIA X TIENDA: las fechas empiezan en {primera.date()} "
            f"pero el archivo es de {periodo[0]}-{periodo[1]:02d}; se usa el período del archivo"
        )
        dias_mes = monthrange(*periodo)[1]
        for item in registros:
            item["dia"] = (
                datetime(item["anio"], item["mes"], item["dia"]) - primera
            ).days + 1
            item["anio"], item["mes"] = periodo
        registros = [item for item in registros if item["dia"] <= dias_mes]

    tiendas_por_codigo = {
        normalizar_texto(tienda.codigo).replace(" ", ""): tienda
        for tienda in Store.query.all()
    }
    periodos = {(item["anio"], item["mes"]) for item in registros}

    # Volver a subir el mismo archivo reemplaza lo que ese archivo cargó antes,
    # aunque haya quedado en otro período.
    (
        DailyStoreSales.query
        .filter_by(nombre_archivo=corte_info["nombre_archivo"])
        .delete(synchronize_session=False)
    )

    # Reimportar el mismo corte reemplaza únicamente ese corte. Los anteriores
    # permanecen disponibles para consultas históricas.
    for anio, mes in periodos:
        (
            DailyStoreSales.query
            .filter_by(
                anio=anio,
                mes=mes,
                dia_corte=corte_info["dia_corte"],
            )
            .delete(synchronize_session=False)
        )

    nuevos = []
    codigos_no_encontrados = set()

    for item in registros:
        tienda = tiendas_por_codigo.get(item["codigo"])
        if not tienda:
            codigos_no_encontrados.add(item["codigo"])
            continue

        nuevos.append(DailyStoreSales(
            store_id=tienda.id,
            anio=item["anio"],
            mes=item["mes"],
            dia=item["dia"],
            venta=item["venta"],
            unidades=item["unidades"],
            dia_corte=corte_info["dia_corte"],
            es_cierre=corte_info["es_cierre"],
            activo=True,
            fecha_carga=datetime.utcnow(),
            nombre_archivo=corte_info["nombre_archivo"],
        ))

    if nuevos:
        db.session.add_all(nuevos)

    if codigos_no_encontrados:
        log_debug(
            "X DIA X TIENDA: códigos sin correspondencia:",
            ", ".join(sorted(codigos_no_encontrados)),
        )

    log_debug(f"X DIA X TIENDA: {len(nuevos)} registros guardados")
    return len(nuevos)


# ==========================================================
# Reporte "Venta por tienda" (bloques Almacén / Fecha Fact / Neto / Cantidad)
# ==========================================================

def _sin_tildes(valor):
    texto = unicodedata.normalize("NFKD", normalizar_texto(valor))
    return "".join(c for c in texto if not unicodedata.combining(c))


def _numero_reporte(valor):
    """Convierte textos como '\xa01,155,600.03' en número."""
    if isinstance(valor, (int, float)) and not pd.isna(valor):
        return float(valor)
    texto = re.sub(r"[^0-9.\-]", "", str(valor or ""))
    try:
        return float(texto) if texto else 0.0
    except ValueError:
        return 0.0


def extraer_venta_por_almacen(ruta):
    """Extrae venta y unidades diarias por tienda sin tocar la base de datos.

    Cada tienda es un bloque de columnas con encabezados Almacén, Fecha Fact,
    Neto, Número facturas y Cantidad, una fila por día.
    """
    registros = []
    hojas_leidas = []

    tablas = []
    with pd.ExcelFile(ruta) as xls:
        for hoja in xls.sheet_names:
            primera_fila = xls.parse(hoja, header=None, nrows=1)
            if primera_fila.empty or not any(
                _sin_tildes(valor).startswith("ALMACEN")
                for valor in primera_fila.iloc[0].tolist()
            ):
                continue
            tablas.append((hoja, xls.parse(hoja, header=None)))

    for hoja, df in tablas:

        encabezados = [_sin_tildes(valor) for valor in df.iloc[0].tolist()]
        bloques = []
        for columna, texto in enumerate(encabezados):
            if not texto.startswith("ALMACEN"):
                continue
            siguientes = encabezados[columna + 1:columna + 6]
            try:
                col_fecha = columna + 1 + next(i for i, t in enumerate(siguientes) if "FECHA" in t)
                col_neto = columna + 1 + next(i for i, t in enumerate(siguientes) if "NETO" in t)
                col_cantidad = columna + 1 + next(i for i, t in enumerate(siguientes) if "CANTIDAD" in t)
            except StopIteration:
                continue
            bloques.append((columna, col_fecha, col_neto, col_cantidad))

        if not bloques:
            continue
        hojas_leidas.append(hoja)

        for col_tienda, col_fecha, col_neto, col_cantidad in bloques:
            for fila in range(1, len(df)):
                nombre_tienda = _sin_tildes(df.iloc[fila, col_tienda])
                codigo = codigo_de_fila(nombre_tienda)
                if not codigo:
                    continue
                try:
                    fecha = pd.to_datetime(
                        str(df.iloc[fila, col_fecha]).replace("\xa0", "").strip(),
                        dayfirst=True,
                        errors="raise",
                    )
                except Exception:
                    continue

                registros.append({
                    "codigo": codigo,
                    "nombre_origen": nombre_tienda,
                    "anio": int(fecha.year),
                    "mes": int(fecha.month),
                    "dia": int(fecha.day),
                    "venta": _numero_reporte(df.iloc[fila, col_neto]),
                    "unidades": int(_numero_reporte(df.iloc[fila, col_cantidad])),
                })

    return registros, hojas_leidas


def importar_venta_por_almacen(ruta, corte_info):
    """Guarda el reporte 'Venta por tienda' en DailyStoreSales.

    Sirve para cargar el histórico del año anterior que alimenta el
    comparativo día por día de Ventas diarias.
    """
    registros, hojas = extraer_venta_por_almacen(ruta)
    if not hojas:
        return 0
    if not registros:
        log_debug("Venta por tienda: no se encontraron datos válidos.")
        return 0

    tiendas_por_codigo = {
        normalizar_texto(tienda.codigo).replace(" ", ""): tienda
        for tienda in Store.query.all()
    }

    # El reporte trae el mes completo: se guarda como el corte del último día
    # del archivo y reemplaza cualquier carga previa de ese mismo corte.
    cortes = {}
    for item in registros:
        clave = (item["anio"], item["mes"])
        cortes[clave] = max(cortes.get(clave, 0), item["dia"])

    for (anio, mes), dia_corte in cortes.items():
        (
            DailyStoreSales.query
            .filter_by(anio=anio, mes=mes, dia_corte=dia_corte)
            .delete(synchronize_session=False)
        )

    nuevos = []
    codigos_no_encontrados = set()
    vistos = set()

    for item in registros:
        tienda = tiendas_por_codigo.get(item["codigo"])
        if not tienda:
            codigos_no_encontrados.add(item["codigo"])
            continue
        clave = (tienda.id, item["anio"], item["mes"], item["dia"])
        if clave in vistos:
            continue
        vistos.add(clave)

        nuevos.append(DailyStoreSales(
            store_id=tienda.id,
            anio=item["anio"],
            mes=item["mes"],
            dia=item["dia"],
            venta=item["venta"],
            unidades=item["unidades"],
            dia_corte=cortes[(item["anio"], item["mes"])],
            es_cierre=corte_info["es_cierre"],
            activo=True,
            fecha_carga=datetime.utcnow(),
            nombre_archivo=corte_info["nombre_archivo"],
        ))

    if nuevos:
        db.session.add_all(nuevos)

    if codigos_no_encontrados:
        log_debug(
            "Venta por tienda: códigos sin correspondencia: "
            + ", ".join(sorted(codigos_no_encontrados))
        )

    log_debug(f"Venta por tienda: {len(nuevos)} registros guardados")
    return len(nuevos)


# ==========================================================
# FUNCIÓN PRINCIPAL DE IMPORTACIÓN
# ==========================================================

def importar_excel_completo(ruta):
    log_debug("=" * 60)
    log_debug("INICIANDO IMPORTACIÓN COMPLETA")
    log_debug(f"Archivo: {ruta}")
    log_debug("=" * 60)
    try:
        if not os.path.exists(ruta):
            raise FileNotFoundError(f"No existe el archivo: {ruta}")
        corte_info = determinar_corte_excel(ruta)
        log_debug("Información del corte:")
        log_debug(corte_info)
        with pd.ExcelFile(ruta) as xls:
            hojas = xls.sheet_names
        log_debug(f"Hojas detectadas: {hojas}")

        total_compliance = 0
        if "CUMPL" in hojas:
            total_compliance = importar_cumplimiento(ruta, corte_info)
        else:
            log_debug("Hoja 'CUMPL' no encontrada. Se omite.")

        total_conversion = 0
        if "CONVERSIÓN_x_DIA" in hojas:
            total_conversion = importar_conversion_diaria(ruta, corte_info)
        else:
            log_debug("Hoja 'CONVERSIÓN_x_DIA' no encontrada. Se omite.")

        total_asesoras = 0
        if "UPT_VPT_ASESOR" in hojas:
            total_asesoras = importar_asesoras(ruta, corte_info)
        else:
            log_debug("Hoja 'UPT_VPT_ASESOR' no encontrada. Se omite.")

        total_metas = 0
        if "METAS_x_LINEA" in hojas:
            total_metas = importar_metas_linea(ruta, corte_info)
        else:
            log_debug("Hoja 'METAS_x_LINEA' no encontrada. Se omite.")

        total_historico = 0
        if "VTA $" in hojas:
            total_historico = importar_historico_lineas(ruta, corte_info)
        else:
            log_debug("Hoja 'VTA $' no encontrada. Se omite.")

        total_xdia = 0
        hojas_norm = [normalizar_texto(h) for h in hojas]
        if any("XDIA" in h.replace(" ", "") for h in hojas_norm):
            total_xdia = importar_xdia(ruta, corte_info)
        else:
            log_debug("Hoja 'X DIA' no encontrada. Se omite.")

        total_xdia_tienda = importar_xdia_tienda(ruta, corte_info)
        total_xdia_tienda += importar_venta_por_almacen(ruta, corte_info)

        archivo_importado = registrar_archivo_importado(ruta, corte_info)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"ERROR EN IMPORTACIÓN: {e}")
        raise

    total = (
        total_compliance
        + total_conversion
        + total_asesoras
        + total_metas
        + total_historico
        + total_xdia
        + total_xdia_tienda
    )
    log_debug("=" * 60)
    log_debug("IMPORTACIÓN COMPLETA FINALIZADA")
    log_debug("=" * 60)
    log_debug(f"Archivo: {corte_info['nombre_archivo']}")
    log_debug(f"Período: {corte_info['anio']}-{corte_info['mes']:02d}")
    log_debug(f"Día de corte: {corte_info['dia_corte']}")
    log_debug(f"Es cierre: {corte_info['es_cierre']}")
    log_debug(f"Compliance: {total_compliance} registros")
    log_debug(f"Conversión diaria: {total_conversion} registros")
    log_debug(f"Asesoras: {total_asesoras} registros")
    log_debug(f"Metas por línea: {total_metas} registros")
    log_debug(f"Histórico ventas línea: {total_historico} registros")
    log_debug(f"X DIA: {total_xdia} registros")
    log_debug(f"X DIA X TIENDA: {total_xdia_tienda} registros")
    log_debug(f"TOTAL: {total} registros")
    log_debug("=" * 60)
    return total
