"""Carga atómica del conjunto oficial, independiente de Compliance."""
from datetime import datetime
from pathlib import Path
import json
import click
from flask.cli import with_appcontext
from sqlalchemy import delete, insert, select, update, and_
from app.extensions import db
from app.models.store import Store
from app.models.trafico_horario import TraficoCarga, TraficoHorario
from app.services.trafico_excel import codigo, leer_historico, leer_cuenta_personas


def guardar_historico(filas, resumen, nombre, aplicar=False):
    tiendas = {}
    for tienda in Store.query.all():
        try:
            cod = codigo(tienda.codigo)
        except ValueError:
            # Registros auxiliares como TOTAL no son ubicaciones del sensor.
            continue
        if cod in tiendas:
            raise ValueError('Código de tienda ambiguo en la BD: ' + cod)
        tiendas[cod] = tienda.id
    desconocidas = sorted({f['codigo'] for f in filas} - tiendas.keys())
    if desconocidas:
        raise ValueError('Tiendas ausentes en la BD: ' + ', '.join(desconocidas))
    if not aplicar:
        return 'Validado; no se guardaron datos'
    try:
        # La migración crea esta fila. Serializa importaciones concurrentes en PostgreSQL.
        nueva_fuente = db.session.get(TraficoCarga, 2)
        if nueva_fuente and nueva_fuente.sha256:
            raise ValueError('El histórico verificado Cuenta_Personas ya está activo; no se puede restaurar la fuente antigua')
        carga = db.session.execute(select(TraficoCarga).where(TraficoCarga.id == 1).with_for_update()).scalar_one()
        if carga.sha256 == resumen['sha256']:
            db.session.rollback()
            return 'Este archivo ya fue importado; sin duplicados'
        db.session.execute(delete(TraficoHorario))
        for start in range(0, len(filas), 2000):
            lote = [{k: v for k, v in f.items() if k != 'codigo'} | {'store_id': tiendas[f['codigo']]} for f in filas[start:start + 2000]]
            db.session.execute(insert(TraficoHorario.__table__), lote)
        carga.sha256 = resumen['sha256']
        carga.nombre_archivo = Path(nombre).name[:255]
        carga.resumen = resumen
        carga.actualizado = datetime.utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return 'Histórico importado correctamente'


def _upsert_trafico(lote):
    dialecto = db.session.get_bind().dialect.name
    if dialecto == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
    elif dialecto == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert as dialect_insert
    else:
        dialect_insert = None
    if dialect_insert:
        stmt = dialect_insert(TraficoHorario.__table__).values(lote)
        stmt = stmt.on_conflict_do_update(
            index_elements=['store_id', 'fecha', 'hora'],
            set_={'trafico': stmt.excluded.trafico, 'sensor_error': False})
        db.session.execute(stmt)
        return
    for item in lote:
        actual = db.session.get(TraficoHorario, (item['store_id'], item['fecha'], item['hora']))
        if actual:
            actual.trafico, actual.sensor_error = item['trafico'], False
        else:
            db.session.add(TraficoHorario(**item))


def guardar_cuenta_personas(filas, resumen, nombre, aplicar=False):
    """Reemplaza solo tráfico horario; conserva todas las facturas existentes."""
    tiendas = {}
    for tienda in Store.query.all():
        try:
            cod = codigo(tienda.codigo)
        except ValueError:
            continue
        if cod in tiendas:
            raise ValueError('Código de tienda ambiguo en la BD: ' + cod)
        tiendas[cod] = tienda.id
    desconocidas = sorted({f['codigo'] for f in filas} - tiendas.keys())
    if desconocidas:
        raise ValueError('Tiendas ausentes en la BD: ' + ', '.join(desconocidas))
    if not aplicar:
        return 'Validado; no se guardaron datos'
    try:
        carga = db.session.execute(
            select(TraficoCarga).where(TraficoCarga.id == 2).with_for_update()
        ).scalar_one()
        if carga.sha256 == resumen['sha256']:
            db.session.rollback()
            return 'Este archivo ya fue importado; sin duplicados'
        # Retira únicamente el tráfico anterior. Las facturas horarias sobreviven.
        db.session.execute(update(TraficoHorario).values(trafico=None, sensor_error=False))
        db.session.execute(delete(TraficoHorario).where(and_(
            TraficoHorario.trafico.is_(None), TraficoHorario.facturas.is_(None))))
        for start in range(0, len(filas), 2000):
            lote = [dict(store_id=tiendas[f['codigo']], fecha=f['fecha'], hora=f['hora'],
                         trafico=f['trafico'], facturas=None, sensor_error=False)
                    for f in filas[start:start + 2000]]
            _upsert_trafico(lote)
        carga.sha256 = resumen['sha256']
        carga.nombre_archivo = Path(nombre).name[:255]
        carga.resumen = resumen
        carga.actualizado = datetime.utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return 'Cuenta_Personas importado; tráfico reemplazado y facturas preservadas'


@click.command('importar-trafico')
@click.argument('archivo', type=click.Path(exists=True, dir_okay=False))
@click.option('--aplicar', is_flag=True, help='Reemplaza atómicamente SOLO el histórico de tráfico de esta pestaña.')
@with_appcontext
def importar_trafico(archivo, aplicar):
    """Valida por defecto. Usar --aplicar para guardar el conjunto completo."""
    click.echo('Leyendo tráfico oficial y facturas; puede tardar varios minutos…')
    try:
        filas, resumen = leer_historico(archivo)
        click.echo(json.dumps(resumen, ensure_ascii=False, indent=2))
        click.echo(guardar_historico(filas, resumen, archivo, aplicar))
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


@click.command('importar-cuenta-personas')
@click.argument('archivo', type=click.Path(exists=True, dir_okay=False))
@click.option('--aplicar', is_flag=True, help='Reemplaza solo el tráfico horario y conserva las facturas.')
@with_appcontext
def importar_cuenta_personas(archivo, aplicar):
    """Valida o carga el histórico verificado de Cuenta_Personas."""
    click.echo('Leyendo Cuenta_Personas; puede tardar varios minutos…')
    try:
        filas, resumen = leer_cuenta_personas(archivo)
        click.echo(json.dumps(resumen, ensure_ascii=False, indent=2))
        click.echo(guardar_cuenta_personas(filas, resumen, archivo, aplicar))
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
