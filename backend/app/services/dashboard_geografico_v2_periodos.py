"""Selección común de periodos del V2; sólo consultas, sin modificar importaciones."""
from calendar import monthrange
from sqlalchemy import func

from app.models.compliance import Compliance
from app.models.store import Store


def opciones_periodo():
    filas = (Compliance.query.with_entities(Compliance.anio, Compliance.mes,
             Compliance.dia_corte).distinct().order_by(
             Compliance.anio.desc(), Compliance.mes.desc(),
             Compliance.dia_corte.desc().nullslast()).all())
    return [{"valor": f"{a:04d}-{m:02d}-" + (f"{d:02d}" if d is not None else "sin-corte"),
             "label": f"{m:02d}/{a} · " + (f"corte {d:02d}" if d is not None else "sin corte registrado"),
             "anio": a, "mes": m, "dia_corte": d} for a, m, d in filas]


def resolver_periodo(anio=None, mes=None, dia_corte=None, periodo=None):
    """Explícito: incluye cortes archivados. Actual: último corte activo global.

    Una recarga del mismo corte se resuelve por activo, fecha_carga e id.
    Nunca se suman versiones ni se mezcla el último corte de cada tienda.
    """
    explicito = bool(periodo and periodo not in ("actual", "anterior"))
    if explicito:
        partes = periodo.split("-", 2)
        if len(partes) != 3:
            raise ValueError("Periodo inválido")
        anio, mes = partes[:2]
        dia_corte = None if partes[2] == "sin-corte" else partes[2]
    if (anio is None) != (mes is None):
        raise ValueError("Indica año y mes juntos")
    if anio is not None:
        try:
            anio, mes = int(anio), int(mes)
            if not 1900 <= anio <= 9999 or not 1 <= mes <= 12:
                raise ValueError()
            if dia_corte is not None:
                dia_corte = int(dia_corte)
                if not 1 <= dia_corte <= monthrange(anio, mes)[1]:
                    raise ValueError()
        except (TypeError, ValueError):
            raise ValueError("Año, mes o corte inválido") from None
    elif dia_corte is not None:
        raise ValueError("El corte requiere año y mes")

    q = Compliance.query
    if anio is not None:
        q = q.filter(Compliance.anio == anio, Compliance.mes == mes)
    if explicito or dia_corte is not None:
        q = q.filter(Compliance.dia_corte == dia_corte)
    else:
        # Conserva la selección actual del sistema cuando hay registros activos.
        activos = q.filter(Compliance.activo.is_(True))
        if activos.first() is not None:
            q = activos
    orden = [Compliance.anio.desc(), Compliance.mes.desc(),
             Compliance.dia_corte.desc().nullslast(),
             Compliance.fecha_carga.desc(), Compliance.id.desc()]
    reg = q.order_by(*orden).first()
    if periodo == "anterior" and reg:
        reg = (Compliance.query.filter(
            (Compliance.anio < reg.anio) |
            ((Compliance.anio == reg.anio) & (Compliance.mes < reg.mes)))
            .order_by(*orden).first())
    if not reg:
        if anio is not None or periodo == "anterior":
            raise ValueError("No hay datos para el periodo solicitado")
        return {"anio": None, "mes": None, "dia_corte": None, "periodo": "", "label": "Sin datos"}
    d = reg.dia_corte
    return {"anio": reg.anio, "mes": reg.mes, "dia_corte": d,
            "periodo": f"{reg.anio:04d}-{reg.mes:02d}-" + (f"{d:02d}" if d is not None else "sin-corte"),
            "label": f"{reg.mes:02d}/{reg.anio} · " + (f"corte {d:02d}" if d is not None else "sin corte registrado")}


def registros_del_corte(seleccion, store_ids=None, solo_total=False):
    if seleccion["anio"] is None or store_ids == []:
        return []
    q = Compliance.query.filter(Compliance.anio == seleccion["anio"],
            Compliance.mes == seleccion["mes"], Compliance.dia_corte == seleccion["dia_corte"])
    if store_ids is not None:
        q = q.filter(Compliance.store_id.in_(store_ids))
    if solo_total:
        q = q.join(Store).filter(func.upper(func.trim(Store.nombre)) == "TOTAL")
    filas = q.order_by(Compliance.activo.desc(), Compliance.fecha_carga.desc(), Compliance.id.desc()).all()
    elegidos = {}
    for r in filas:
        elegidos.setdefault(r.store_id, r)
    return list(elegidos.values())
