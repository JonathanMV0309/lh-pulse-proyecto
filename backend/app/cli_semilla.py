"""flask --app run sembrar: crea las tablas y, si la base está vacía, la llena con datos de ejemplo.

Todos los datos son inventados (tiendas «Ejemplo», correos @lhpulse.test). La clave del administrador
de ejemplo sale del .env (SEMILLA_ADMIN_CLAVE): nunca se escribe en el código.
Docker Compose lo ejecuta al arrancar la API; si la base ya tiene datos, no cambia nada.
"""
import calendar
import os
import random
from datetime import date, datetime

import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

TIENDAS = [
    ("S-01", "Tienda Norte Ejemplo", "Bogotá", "frio"), ("S-02", "Tienda Sur Ejemplo", "Bogotá", "frio"),
    ("S-03", "Tienda Centro Ejemplo", "Bogotá", "frio"), ("S-04", "Outlet Ejemplo", "Bogotá", "frio"),
    ("S-05", "Tienda Poblado Ejemplo", "Medellín", "templado"), ("S-06", "Tienda Laureles Ejemplo", "Medellín", "templado"),
    ("S-07", "Tienda Chipichape Ejemplo", "Cali", "caliente"), ("S-08", "Tienda Unicentro Ejemplo", "Cali", "caliente"),
    ("S-09", "Tienda Buenavista Ejemplo", "Barranquilla", "caliente"), ("S-10", "Tienda Cabecera Ejemplo", "Bucaramanga", "templado"),
]


@click.command("sembrar")
@with_appcontext
def sembrar():
    from app.extensions import db
    from app.models import Compliance, Role, Store, User
    from app.models.meta_tienda import MetaTienda, MetaTiendaHistorial

    db.create_all()
    if Store.query.first():
        click.echo("La base ya tiene datos: no se siembra nada.")
        return
    clave = os.getenv("SEMILLA_ADMIN_CLAVE")
    if not clave:
        raise click.ClickException("Falta SEMILLA_ADMIN_CLAVE en el .env (la clave del administrador de ejemplo).")
    correo = os.getenv("SEMILLA_ADMIN_CORREO", "admin@lhpulse.test")

    admin, tienda = Role(nombre="Administrador"), Role(nombre="TIENDA")
    db.session.add_all([admin, tienda])
    db.session.flush()
    tiendas = []
    for codigo, nombre, ciudad, clima in TIENDAS:
        s = Store(codigo=codigo, nombre=nombre, ciudad=ciudad, clima=clima, estado="ACTIVA")
        db.session.add(s)
        tiendas.append(s)
    db.session.add(Store(codigo="S-99", nombre="Tienda Cerrada Ejemplo", ciudad="Bogotá", estado="INACTIVA"))
    db.session.flush()
    db.session.add(User(nombre="Administración Ejemplo", correo=correo, password=generate_password_hash(clave), role_id=admin.id))

    # Ventas del mes actual (informes al día de corte de hoy) y metas para 8 de las 10 tiendas
    hoy = date.today()
    dias = calendar.monthrange(hoy.year, hoy.month)[1]
    corte = max(1, hoy.day - 1)
    azar = random.Random(2026)
    for s in tiendas:
        meta = azar.randrange(40, 120) * 1_000_000
        avance = azar.uniform(0.7, 1.25) * corte / dias          # unas van adelante y otras atrasadas
        venta = round(meta * avance, -3)
        db.session.add(Compliance(store_id=s.id, anio=hoy.year, mes=hoy.month, dia_corte=corte, venta_actual=venta,
                                  venta_anterior=venta * 0.9, incremento=0.11, cuota_total=meta,
                                  cumplimiento_pct=venta / meta, facturas=int(venta / 95_000),
                                  es_cierre=False, activo=True, fecha_carga=datetime.utcnow()))
        if s.codigo not in ("S-09", "S-10"):
            m = MetaTienda(store_id=s.id, anio=hoy.year, mes=hoy.month, valor=meta, nota="Meta inicial de ejemplo",
                           actualizado_por="Semilla")
            db.session.add(m)
            db.session.flush()
            db.session.add(MetaTiendaHistorial(meta_id=m.id, store_id=s.id, anio=hoy.year, mes=hoy.month, accion="creada",
                                               valor_nuevo=meta, usuario="Semilla"))
    db.session.commit()
    click.echo(f"Listo: {len(tiendas)} tiendas de ejemplo, ventas de {hoy.month:02d}/{hoy.year} y metas. Admin: {correo}")
