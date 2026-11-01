from datetime import datetime

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Advisor, AdvisorGoal, AdvisorPerformance, Compliance, Store


TIPO_FIJA = "FIJA"
TIPO_AUXILIAR = "AUXILIAR"
TIPOS_ASESORA = {TIPO_FIJA, TIPO_AUXILIAR}


def _normalizar_meta(valor):
    try:
        return max(float(valor or 0), 0.0)
    except (TypeError, ValueError):
        return 0.0


def _normalizar_tipo(valor, nombre=None):
    tipo = str(valor or "").strip().upper()
    if tipo in TIPOS_ASESORA:
        return tipo
    nombre = str(nombre or "").strip().upper()
    return TIPO_AUXILIAR if "ASESOR AUX" in nombre else TIPO_FIJA


def _es_vendedor_unico(nombre):
    return "VENDEDOR UNICO" in str(nombre or "").strip().upper()


def obtener_meta(advisor_id, store_id, anio, mes):
    return AdvisorGoal.query.filter_by(
        advisor_id=advisor_id, store_id=store_id, anio=anio, mes=mes
    ).first()


def obtener_metas_tienda(store_id, anio, mes):
    return (
        AdvisorGoal.query
        .filter_by(store_id=store_id, anio=anio, mes=mes)
        .order_by(AdvisorGoal.meta_venta.desc())
        .all()
    )


def _filas_periodo(store_id, anio, mes, filtro_nombre=None):
    query = (
        db.session.query(
            AdvisorPerformance.advisor_id,
            Advisor.nombre,
            func.sum(AdvisorPerformance.venta).label("venta_total"),
            func.sum(AdvisorPerformance.unidades).label("unidades_total"),
            func.sum(AdvisorPerformance.facturas).label("facturas_total"),
        )
        .join(Advisor, Advisor.id == AdvisorPerformance.advisor_id)
        .filter(
            AdvisorPerformance.store_id == store_id,
            AdvisorPerformance.anio == anio,
            AdvisorPerformance.mes == mes,
            AdvisorPerformance.activo.is_(True),
            Advisor.estado == "ACTIVO",
            AdvisorPerformance.venta >= 0,
        )
    )
    if filtro_nombre:
        query = query.filter(Advisor.nombre.ilike(f"%{filtro_nombre.strip()}%"))

    return (
        query.group_by(AdvisorPerformance.advisor_id, Advisor.nombre)
        .order_by(func.sum(AdvisorPerformance.venta).desc(), Advisor.nombre.asc())
        .all()
    )


def obtener_asesoras_validas_para_meta(store_id, anio, mes):
    metas = {m.advisor_id: m for m in obtener_metas_tienda(store_id, anio, mes)}
    resultado = []
    for row in _filas_periodo(store_id, anio, mes):
        if _es_vendedor_unico(row.nombre):
            continue
        meta = metas.get(row.advisor_id)
        tipo = _normalizar_tipo(
            getattr(meta, "tipo_asesora", None) if meta else None,
            row.nombre,
        )
        resultado.append({
            "advisor_id": row.advisor_id,
            "nombre": row.nombre,
            "venta": float(row.venta_total or 0),
            "unidades": float(row.unidades_total or 0),
            "facturas": float(row.facturas_total or 0),
            "tipo_asesora": tipo,
            "meta_obj": meta,
        })
    return resultado


def obtener_venta_asesor_aux(store_id, anio, mes):
    return sum(
        item["venta"]
        for item in obtener_asesoras_validas_para_meta(store_id, anio, mes)
        if item["tipo_asesora"] == TIPO_AUXILIAR
    )


def obtener_cantidad_asesoras_fijas(store_id, anio=None, mes=None):
    if anio is None or mes is None:
        return (
            Advisor.query
            .filter(Advisor.store_id == store_id, Advisor.estado == "ACTIVO")
            .filter(~func.upper(Advisor.nombre).like("%VENDEDOR UNICO%"))
            .count()
        )
    return sum(
        1 for item in obtener_asesoras_validas_para_meta(store_id, anio, mes)
        if item["tipo_asesora"] == TIPO_FIJA
    )


def obtener_cantidad_asesoras_fijas_por_codigo(codigo_tienda):
    store = Store.query.filter(func.upper(Store.codigo) == str(codigo_tienda).strip().upper()).first()
    return obtener_cantidad_asesoras_fijas(store.id) if store else 0


def obtener_meta_tienda(store_id, anio, mes):
    compliance = (
        Compliance.query
        .filter(
            Compliance.store_id == store_id,
            Compliance.anio == anio,
            Compliance.mes == mes,
            Compliance.activo.is_(True),
        )
        .order_by(Compliance.id.desc())
        .first()
    )
    return float(compliance.cuota_total or 0) if compliance else 0.0


def calcular_metas_asesoras(
    store_id, anio, mes, meta_tienda, venta_asesor_aux=None
):
    asesoras = obtener_asesoras_validas_para_meta(store_id, anio, mes)
    meta_tienda = _normalizar_meta(meta_tienda)

    venta_aux_real = sum(
        item["venta"] for item in asesoras
        if item["tipo_asesora"] == TIPO_AUXILIAR
    )
    # Se conserva el parámetro por compatibilidad con las rutas antiguas. La
    # pantalla unificada siempre usa la venta real importada.
    venta_aux_aplicada = (
        venta_aux_real if venta_asesor_aux is None
        else _normalizar_meta(venta_asesor_aux)
    )
    meta_ajustada = max(meta_tienda - venta_aux_aplicada, 0.0)
    fijas = [a for a in asesoras if a["tipo_asesora"] == TIPO_FIJA]
    meta_por_asesora = meta_ajustada / len(fijas) if fijas else 0.0

    resultado = []
    for asesora in asesoras:
        meta_obj = asesora["meta_obj"]
        if asesora["tipo_asesora"] == TIPO_AUXILIAR:
            meta_final = 0.0
        elif meta_obj and float(meta_obj.meta_venta or 0) > 0:
            meta_final = float(meta_obj.meta_venta)
        else:
            meta_final = meta_por_asesora

        resultado.append({
            **{k: v for k, v in asesora.items() if k != "meta_obj"},
            "meta": meta_final,
            "meta_venta": meta_final,
            "cumplimiento_meta": (
                asesora["venta"] / meta_final if meta_final > 0 else None
            ),
        })

    ultima_actualizacion = max(
        (m.updated_at for m in obtener_metas_tienda(store_id, anio, mes) if m.updated_at),
        default=None,
    )
    return {
        "meta_tienda": meta_tienda,
        "venta_asesor_aux": venta_aux_aplicada,
        "venta_auxiliar_real": venta_aux_real,
        "meta_ajustada": meta_ajustada,
        "cantidad_asesoras": len(fijas),
        "cantidad_auxiliares": len(asesoras) - len(fijas),
        "meta_por_asesora": meta_por_asesora,
        "asesoras": resultado,
        "ultima_actualizacion": ultima_actualizacion,
    }


def guardar_meta(
    advisor_id, store_id, anio, mes, meta_venta,
    tipo_asesora=TIPO_FIJA, updated_by_user_id=None, commit=True,
):
    try:
        advisor_id, store_id, anio, mes = map(
            int, (advisor_id, store_id, anio, mes)
        )
        meta_venta = float(meta_venta or 0)
    except (TypeError, ValueError):
        return None, "Los datos de la meta no son válidos.", False

    if mes not in range(1, 13) or meta_venta < 0:
        return None, "El período o la meta no son válidos.", False

    advisor = db.session.get(Advisor, advisor_id)
    if not advisor or _es_vendedor_unico(advisor.nombre):
        return None, "Asesora no válida para distribución.", False

    tipo = _normalizar_tipo(tipo_asesora, advisor.nombre)
    if tipo == TIPO_AUXILIAR:
        meta_venta = 0.0

    meta = obtener_meta(advisor_id, store_id, anio, mes)
    if not meta:
        meta = AdvisorGoal(
            advisor_id=advisor_id, store_id=store_id, anio=anio, mes=mes
        )
        db.session.add(meta)

    meta.meta_venta = meta_venta
    meta.tipo_asesora = tipo
    meta.updated_by_user_id = updated_by_user_id
    meta.updated_at = datetime.utcnow()

    if not commit:
        return meta, "Meta preparada.", True
    try:
        db.session.commit()
        return meta, "Meta guardada correctamente.", True
    except SQLAlchemyError as exc:
        db.session.rollback()
        return None, f"Error al guardar la meta: {exc}", False


def guardar_distribucion_periodo(
    store_id, anio, mes, asignaciones, updated_by_user_id
):
    validas = {
        item["advisor_id"]: item
        for item in obtener_asesoras_validas_para_meta(store_id, anio, mes)
    }
    recibidas = set()
    try:
        for item in asignaciones:
            advisor_id = int(item.get("advisor_id"))
            if advisor_id not in validas or advisor_id in recibidas:
                raise ValueError("La distribución contiene una asesora inválida o repetida.")
            recibidas.add(advisor_id)
            tipo = _normalizar_tipo(item.get("tipo_asesora"), validas[advisor_id]["nombre"])
            meta_venta = 0 if tipo == TIPO_AUXILIAR else float(item.get("meta_venta") or 0)
            if meta_venta < 0:
                raise ValueError("Las metas no pueden ser negativas.")
            _, mensaje, ok = guardar_meta(
                advisor_id, store_id, anio, mes, meta_venta,
                tipo_asesora=tipo,
                updated_by_user_id=updated_by_user_id,
                commit=False,
            )
            if not ok:
                raise ValueError(mensaje)

        if recibidas != set(validas):
            raise ValueError("Debes guardar la clasificación de todas las asesoras visibles.")

        db.session.commit()
        return len(recibidas), None
    except (SQLAlchemyError, TypeError, ValueError) as exc:
        db.session.rollback()
        return 0, str(exc)


def eliminar_meta(advisor_id, store_id, anio, mes):
    meta = obtener_meta(advisor_id, store_id, anio, mes)
    if not meta:
        return "No existe una meta para eliminar.", False
    try:
        db.session.delete(meta)
        db.session.commit()
        return "Meta eliminada correctamente.", True
    except SQLAlchemyError as exc:
        db.session.rollback()
        return f"Error al eliminar la meta: {exc}", False


def obtener_asesoras_para_administrar_metas(
    store_id, anio, mes, filtro_nombre=None
):
    distribucion = calcular_metas_asesoras(
        store_id, anio, mes, obtener_meta_tienda(store_id, anio, mes)
    )
    filtro = str(filtro_nombre or "").strip().lower()
    resultado = []
    for item in distribucion["asesoras"]:
        if filtro and filtro not in item["nombre"].lower():
            continue
        resultado.append({
            **item,
            "meta_obj": obtener_meta(item["advisor_id"], store_id, anio, mes),
            "meta_valor": item["meta"],
        })
    return resultado


def obtener_asesoras_con_venta_y_meta(
    store_id, anio, mes, filtro_nombre=None
):
    resultado = obtener_asesoras_para_administrar_metas(
        store_id, anio, mes, filtro_nombre
    )
    for item in resultado:
        venta = item["venta"]
        facturas = item.get("facturas", 0)
        unidades = item.get("unidades", 0)
        meta = item["meta_valor"]
        item.update({
            "ticket_promedio": venta / facturas if facturas else 0,
            "upt": unidades / facturas if facturas else 0,
            "falta_meta": max(meta - venta, 0),
            "estado_meta": (
                "AUXILIAR" if item["tipo_asesora"] == TIPO_AUXILIAR
                else "META SUPERADA" if meta and venta >= meta
                else "EN PROGRESO" if meta
                else "SIN META"
            ),
            "clase_meta": (
                "secondary" if item["tipo_asesora"] == TIPO_AUXILIAR
                else "success" if meta and venta >= meta
                else "warning" if meta
                else "secondary"
            ),
        })
    return resultado

