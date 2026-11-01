"""Cumplimientos e incrementos acumulados por tienda (hoja «ACUM» del Excel de ventas).

Se lee directamente del último archivo cargado: no guarda nada en la base de datos.
La hoja trae, por tienda y mes, el cumplimiento de la cuota y el incremento frente al año
anterior, de 2022 en adelante. Los años y meses se toman de los encabezados (cada mes se
agrega una columna, así que no se usan posiciones fijas).
"""
import glob
import os
import threading

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
_cache = {}
_lock = threading.Lock()


def _backend():
    from flask import current_app
    return os.path.dirname(current_app.root_path)


def _con_acum(ruta):
    try:
        import pandas as pd
        with pd.ExcelFile(ruta) as xls:
            return "ACUM" in xls.sheet_names
    except Exception:
        return False


def archivo_actual():
    """El último Excel cargado que tenga la hoja ACUM (o el más reciente de la carpeta uploads)."""
    from app.models.archivo_importado import ArchivoImportado
    base = _backend()
    for a in ArchivoImportado.query.order_by(ArchivoImportado.id.desc()).limit(10).all():
        for ruta in (a.ruta or "", os.path.join(base, a.ruta or "")):
            if ruta and os.path.isfile(ruta) and _con_acum(ruta):
                return ruta, a.nombre_archivo
    archivos = sorted(glob.glob(os.path.join(base, "uploads", "**", "*.xlsx"), recursive=True), key=os.path.getmtime, reverse=True)
    for ruta in archivos[:10]:
        if _con_acum(ruta):
            return ruta, os.path.basename(ruta)
    return None, None


def _numero(v):
    try:
        import math
        x = float(v)
        return None if math.isnan(x) else x
    except (TypeError, ValueError):
        return None


def leer(ruta):
    """{"anios": [...], "tiendas": [{codigo, nombre, store_id, cumplimiento: {anio: [12]}, incremento: {...}}], "total": {...}}"""
    import pandas as pd
    from app.services.import_service import buscar_tienda
    df = pd.read_excel(ruta, sheet_name="ACUM", header=None)
    # Encabezados: la fila con «TIENDA» tiene los meses; la de arriba, los años; «INCREMENTOS» marca dónde empiezan
    fila_mes = next(i for i in range(min(12, len(df))) if any(str(v).strip().upper() == "TIENDA" for v in df.iloc[i].tolist()))
    fila_anio = fila_mes - 1
    inicio_inc = None
    for i in range(fila_mes):
        for j, v in enumerate(df.iloc[i].tolist()):
            if "INCREMENTO" in str(v).upper():
                inicio_inc = j
    columnas, anio = [], None
    for j in range(df.shape[1]):
        a = df.iat[fila_anio, j]
        try:
            a = int(float(a))
            if 2000 < a < 2100:
                anio = a
        except (TypeError, ValueError):
            pass
        mes = str(df.iat[fila_mes, j]).strip()[:3].capitalize()
        if anio and mes in MESES:
            tipo = "incremento" if inicio_inc is not None and j >= inicio_inc else "cumplimiento"
            columnas.append((j, tipo, anio, MESES.index(mes)))
    anios = sorted({c[2] for c in columnas})
    col_nombre = next(j for j, v in enumerate(df.iloc[fila_mes].tolist()) if str(v).strip().upper() == "TIENDA")

    tiendas, total = [], None
    for i in range(fila_mes + 1, len(df)):
        codigo = str(df.iat[i, 0]).strip() if col_nombre > 0 else ""
        nombre = str(df.iat[i, col_nombre]).strip()
        if nombre in ("", "nan") and codigo in ("", "nan"):
            continue
        fila = {"codigo": codigo, "nombre": nombre, "cumplimiento": {}, "incremento": {}}
        for j, tipo, a, m in columnas:
            fila[tipo].setdefault(a, [None] * 12)[m] = _numero(df.iat[i, j])
        if "TOTAL" in nombre.upper() or codigo.upper().startswith("TOT"):
            fila["nombre"] = "Total de la red"
            total = fila
            continue
        tienda = buscar_tienda(codigo) or buscar_tienda(nombre)
        fila["store_id"] = tienda.id if tienda else None
        fila["codigo"] = (tienda.codigo if tienda else codigo.replace(" ", "-"))
        # Sin ningún dato (como una tienda que ya no reporta): no se muestra
        if any(v is not None for t in ("cumplimiento", "incremento") for vals in fila[t].values() for v in vals):
            tiendas.append(fila)
    return {"anios": anios, "tiendas": tiendas, "total": total}


def datos():
    """Lo de la hoja ACUM del último archivo, guardado en memoria mientras el archivo no cambie."""
    ruta, nombre = archivo_actual()
    if not ruta:
        return None
    clave = (ruta, os.path.getmtime(ruta))
    with _lock:
        if clave not in _cache:
            _cache.clear()
            d = leer(ruta)
            d["archivo"] = nombre
            _cache[clave] = d
        return _cache[clave]
