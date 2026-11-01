"""Lectura del histórico ACIDA. No escribe en la base de datos."""
from collections import Counter
from datetime import date, datetime, time
from hashlib import sha256
from math import isfinite
from pathlib import Path
import re

from openpyxl import load_workbook

FUENTE = 'BASE_DESCARGA_16_MAR'
FUENTE_CUENTA_PERSONAS = 'Cuenta_Personas'


def codigo(valor):
    match = re.match(r'^S[\s-]*(\d+)(?:\b|$)', str(valor or '').strip().upper())
    if not match:
        raise ValueError('Código de tienda no reconocido: ' + str(valor))
    return 'S-' + match.group(1).zfill(2)


def entero(valor):
    if isinstance(valor, bool):
        raise ValueError('Conteo booleano inválido')
    n = float(valor)
    if not isfinite(n) or n < 0 or not n.is_integer():
        raise ValueError('Se requiere un conteo entero no negativo')
    return int(n)


def hora(valor):
    if isinstance(valor, (datetime, time)):
        return valor.hour
    if isinstance(valor, (int, float)) and 0 <= valor < 1:
        return int(valor * 24)
    return time.fromisoformat(str(valor).strip()).hour


def leer_historico(ruta):
    ruta = Path(ruta)
    digest = sha256()
    with ruta.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    wb = load_workbook(ruta, read_only=True, data_only=True, keep_links=False)
    filas = {}
    resumen = Counter()
    sensores = {}
    errores = set()
    try:
        for nombre in (FUENTE, 'BASE', 'TABLAS'):
            if nombre not in wb.sheetnames:
                raise ValueError('Falta la hoja ' + nombre)
        for row in wb['TABLAS'].iter_rows(min_row=2, max_col=13, values_only=True):
            if str(row[12] or '').strip().upper() == 'SI':
                errores.add((codigo(row[8]), date(int(row[11]), int(row[10]), int(row[9]))))

        def registro(cod, fecha, hh):
            return filas.setdefault((cod, fecha, hh), {
                'codigo': cod, 'fecha': fecha, 'hora': hh,
                'trafico': None, 'facturas': None,
                'sensor_error': (cod, fecha) in errores,
            })

        for numero, row in enumerate(wb[FUENTE].iter_rows(min_row=2, max_col=4, values_only=True), 2):
            if all(v is None for v in row):
                continue
            try:
                sensor, fecha, hh, contador = row
                cod = codigo(sensor)
                if isinstance(fecha, datetime):
                    fecha = fecha.date()
                if not isinstance(fecha, date):
                    raise ValueError('Fecha Excel inválida')
                hh, contador = hora(hh), entero(contador)
                # El origen es horario: dos sensores para una tienda/hora necesitan revisión.
                clave = (cod, fecha, hh)
                if clave in sensores:
                    if sensores[clave] != (sensor, contador):
                        raise ValueError('Conteos o sensores en conflicto para la misma tienda/hora')
                    resumen['duplicados_trafico_omitidos'] += 1
                    continue
                sensores[clave] = (sensor, contador)
                registro(cod, fecha, hh)['trafico'] = contador
                resumen['filas_trafico'] += 1
            except (ValueError, TypeError, OverflowError) as exc:
                raise ValueError(f'{FUENTE}, fila {numero}: {exc}') from exc

        encabezados = next(wb['BASE'].iter_rows(max_row=1, max_col=7, values_only=True))
        if tuple(str(v).strip().upper() for v in encabezados) != (
            'TIENDA', 'DIA', 'MES', 'AÑO', 'FACTURA', 'T_SISTEMA', 'CONTADOR'
        ):
            raise ValueError('La estructura de BASE cambió; revisar antes de importar')
        for numero, row in enumerate(wb['BASE'].iter_rows(min_row=2, max_col=7, values_only=True), 2):
            # Solo conteos de facturas. Nunca importar el tráfico antiguo de BASE.
            if row[4] is None:
                continue
            try:
                cod = codigo(row[0])
                fecha = date(int(row[3]), int(row[2]), int(row[1]))
                n = entero(row[4])
                item = registro(cod, fecha, hora(row[5]))
                # Filas iguales pueden representar facturas distintas en el mismo minuto.
                item['facturas'] = (item['facturas'] or 0) + n
                resumen['filas_facturas'] += 1
            except (ValueError, TypeError, OverflowError) as exc:
                raise ValueError(f'BASE, fila {numero}: {exc}') from exc
    finally:
        wb.close()
    if not sensores or not resumen['filas_facturas']:
        raise ValueError('El archivo debe contener tráfico y facturas')
    valores = list(filas.values())
    resumen.update({
        'horas_tienda': len(valores), 'tiendas': len({v['codigo'] for v in valores}),
        'trafico': sum(v['trafico'] or 0 for v in valores),
        'facturas': sum(v['facturas'] or 0 for v in valores),
        'horas_con_error_sensor': sum(v['sensor_error'] for v in valores),
        'horas_coincidentes': sum(v['trafico'] is not None and v['facturas'] is not None and not v['sensor_error'] for v in valores),
    })
    report = dict(resumen)
    for campo in ('trafico', 'facturas'):
        fechas = [v['fecha'] for v in valores if v[campo] is not None]
        report[campo + '_desde'] = min(fechas).isoformat()
        report[campo + '_hasta'] = max(fechas).isoformat()
    report['sha256'] = digest.hexdigest()
    report['fuente_trafico'] = FUENTE
    report['fuente_facturas'] = 'BASE: columna factura (conteos), sin Contador'
    return valores, report


def leer_cuenta_personas(ruta):
    """Lee el nuevo histórico verificado de tráfico, sin tocar facturas."""
    ruta = Path(ruta)
    digest = sha256()
    with ruta.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    wb = load_workbook(ruta, read_only=True, data_only=True, keep_links=False)
    filas, vistos, resumen = [], {}, Counter()
    try:
        if FUENTE_CUENTA_PERSONAS not in wb.sheetnames:
            raise ValueError('Falta la hoja ' + FUENTE_CUENTA_PERSONAS)
        ws = wb[FUENTE_CUENTA_PERSONAS]
        headers = next(ws.iter_rows(max_row=1, max_col=9, values_only=True))
        esperados = ('COD_FECHA', 'TIENDA', 'DIA', 'MES', 'AÑO',
                     'TIENDA - CUENTA PERSONAS', 'FECHA', 'HORA', 'CONTADOR')
        if tuple(str(v or '').strip().upper() for v in headers) != esperados:
            raise ValueError('La estructura de Cuenta_Personas cambió; revisar antes de importar')
        vacias = 0
        for numero, row in enumerate(ws.iter_rows(min_row=2, max_col=9, values_only=True), 2):
            if all(v is None for v in row):
                vacias += 1
                # El archivo trae formato hasta la fila 1.048.576.
                if vacias >= 5000:
                    break
                continue
            vacias = 0
            try:
                cod = codigo(row[1])
                fecha = row[6]
                if isinstance(fecha, datetime):
                    fecha = fecha.date()
                if not isinstance(fecha, date):
                    fecha = datetime.strptime(str(fecha).strip(), '%d/%m/%Y').date()
                hh, contador = hora(row[7]), entero(row[8])
                if (int(row[2]), int(row[3]), int(row[4])) != (fecha.day, fecha.month, fecha.year):
                    raise ValueError('DÍA/MES/AÑO no coincide con Fecha')
                clave = (cod, fecha, hh)
                if clave in vistos:
                    if vistos[clave] != contador:
                        raise ValueError('Conteos en conflicto para la misma tienda/fecha/hora')
                    resumen['duplicados_omitidos'] += 1
                    continue
                vistos[clave] = contador
                filas.append(dict(codigo=cod, fecha=fecha, hora=hh, trafico=contador,
                                  facturas=None, sensor_error=False))
                resumen['filas_trafico'] += 1
            except (ValueError, TypeError, OverflowError) as exc:
                raise ValueError(f'{FUENTE_CUENTA_PERSONAS}, fila {numero}: {exc}') from exc
    finally:
        wb.close()
    if not filas:
        raise ValueError('Cuenta_Personas no contiene registros válidos')
    fechas = [v['fecha'] for v in filas]
    report = dict(resumen)
    report.update({
        'horas_tienda': len(filas),
        'tiendas': len({v['codigo'] for v in filas}),
        'trafico': sum(v['trafico'] for v in filas),
        'trafico_desde': min(fechas).isoformat(),
        'trafico_hasta': max(fechas).isoformat(),
        'sha256': digest.hexdigest(),
        'fuente_trafico': FUENTE_CUENTA_PERSONAS,
        'facturas_preservadas': True,
    })
    return filas, report
