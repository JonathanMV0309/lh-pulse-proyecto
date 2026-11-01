"""DAO con SQLAlchemy (PostgreSQL en Docker). Es el único lugar del módulo que usa db.session.

Usar el ORM no reemplaza al DAO: aquí se encapsulan las consultas y los commit, y hacia afuera
solo salen DTO.
"""
from app.extensions import db
from app.metas.dao.base import HistorialDAO, MetaDAO, TiendaDAO
from app.metas.dto import HistorialDTO, MetaDTO, TiendaDTO
from app.models.meta_tienda import MetaTienda, MetaTiendaHistorial
from app.models.store import Store


def _tienda_dto(s):
    return TiendaDTO(id=s.id, codigo=s.codigo, nombre=s.nombre, ciudad=s.ciudad or "")


def _meta_dto(m):
    return MetaDTO(id=m.id, tienda_id=m.store_id, anio=m.anio, mes=m.mes, valor=float(m.valor), nota=m.nota or "",
                   actualizado_por=m.actualizado_por or "", actualizado_en=m.actualizado_en,
                   tienda_codigo=m.store.codigo if m.store else "", tienda_nombre=m.store.nombre if m.store else "")


class TiendaDAOSQLAlchemy(TiendaDAO):

    def listar_activas(self):
        filas = (Store.query.filter(Store.estado == "ACTIVA", Store.codigo.like("S-%"))
                 .order_by(Store.codigo).all())
        return [_tienda_dto(s) for s in filas]

    def obtener(self, tienda_id):
        s = db.session.get(Store, tienda_id)
        return _tienda_dto(s) if s and s.estado == "ACTIVA" else None


class MetaDAOSQLAlchemy(MetaDAO):

    def listar_periodo(self, anio, mes):
        return [_meta_dto(m) for m in MetaTienda.query.filter_by(anio=anio, mes=mes).all()]

    def obtener(self, meta_id):
        m = db.session.get(MetaTienda, meta_id)
        return _meta_dto(m) if m else None

    def buscar(self, tienda_id, anio, mes):
        m = MetaTienda.query.filter_by(store_id=tienda_id, anio=anio, mes=mes).first()
        return _meta_dto(m) if m else None

    def crear(self, entrada, usuario):
        m = MetaTienda(store_id=entrada.tienda_id, anio=entrada.anio, mes=entrada.mes, valor=entrada.valor,
                       nota=entrada.nota, actualizado_por=usuario)
        db.session.add(m)
        db.session.commit()
        return _meta_dto(m)

    def actualizar(self, meta_id, entrada, usuario):
        m = db.session.get(MetaTienda, meta_id)
        if not m:
            return None
        m.valor = entrada.valor
        m.nota = entrada.nota
        m.actualizado_por = usuario
        db.session.commit()
        return _meta_dto(m)

    def eliminar(self, meta_id):
        m = db.session.get(MetaTienda, meta_id)
        if not m:
            return False
        db.session.delete(m)
        db.session.commit()
        return True


class HistorialDAOSQLAlchemy(HistorialDAO):

    def registrar(self, meta_id, tienda_id, anio, mes, accion, valor_anterior, valor_nuevo, usuario):
        db.session.add(MetaTiendaHistorial(meta_id=meta_id, store_id=tienda_id, anio=anio, mes=mes, accion=accion,
                                           valor_anterior=valor_anterior, valor_nuevo=valor_nuevo, usuario=usuario))
        db.session.commit()

    def listar(self, meta_id):
        filas = (MetaTiendaHistorial.query.filter_by(meta_id=meta_id)
                 .order_by(MetaTiendaHistorial.fecha.desc(), MetaTiendaHistorial.id.desc()).all())
        return [HistorialDTO(accion=h.accion, usuario=h.usuario or "", fecha=h.fecha,
                             valor_anterior=float(h.valor_anterior) if h.valor_anterior is not None else None,
                             valor_nuevo=float(h.valor_nuevo) if h.valor_nuevo is not None else None) for h in filas]
