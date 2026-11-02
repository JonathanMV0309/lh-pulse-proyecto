"""DAO en memoria: cumplen los mismos contratos sin base de datos (pruebas unitarias y demos rápidas)."""
from dataclasses import replace
from datetime import datetime

from app.metas.dao.base import HistorialDAO, MetaDAO, TiendaDAO, VentaDAO
from app.metas.dto import HistorialDTO, MetaDTO, TiendaDTO, VentaMesDTO


class TiendaDAOMemoria(TiendaDAO):

    def __init__(self, tiendas=None):
        self.tiendas = {t.id: t for t in (tiendas or [])}
        self.consultas = 0              # cuántas veces se leyó la "base": sirve para probar la caché

    def listar_activas(self):
        self.consultas += 1
        return sorted(self.tiendas.values(), key=lambda t: t.codigo)

    def obtener(self, tienda_id):
        return self.tiendas.get(tienda_id)


class MetaDAOMemoria(MetaDAO):

    def __init__(self, tiendas_dao):
        self.metas, self.siguiente, self.tiendas_dao = {}, 1, tiendas_dao

    def _completa(self, m):
        # Devuelve una copia, igual que el DAO de base de datos: quien la reciba no cambia lo guardado
        t = self.tiendas_dao.obtener(m.tienda_id) or TiendaDTO(m.tienda_id, "", "")
        return replace(m, tienda_codigo=t.codigo, tienda_nombre=t.nombre)

    def listar_periodo(self, anio, mes):
        return [self._completa(m) for m in self.metas.values() if m.anio == anio and m.mes == mes]

    def obtener(self, meta_id):
        m = self.metas.get(meta_id)
        return self._completa(m) if m else None

    def buscar(self, tienda_id, anio, mes):
        return next((self._completa(m) for m in self.metas.values()
                     if (m.tienda_id, m.anio, m.mes) == (tienda_id, anio, mes)), None)

    def crear(self, entrada, usuario):
        m = MetaDTO(id=self.siguiente, tienda_id=entrada.tienda_id, anio=entrada.anio, mes=entrada.mes,
                    valor=entrada.valor, nota=entrada.nota, actualizado_por=usuario, actualizado_en=datetime.now())
        self.metas[m.id] = m
        self.siguiente += 1
        return self._completa(m)

    def actualizar(self, meta_id, entrada, usuario):
        m = self.metas.get(meta_id)
        if not m:
            return None
        m.valor, m.nota, m.actualizado_por, m.actualizado_en = entrada.valor, entrada.nota, usuario, datetime.now()
        return self._completa(m)

    def eliminar(self, meta_id):
        return self.metas.pop(meta_id, None) is not None


class HistorialDAOMemoria(HistorialDAO):

    def __init__(self):
        self.filas = []

    def registrar(self, meta_id, tienda_id, anio, mes, accion, valor_anterior, valor_nuevo, usuario):
        self.filas.append((meta_id, HistorialDTO(accion, valor_anterior, valor_nuevo, usuario, datetime.now())))

    def listar(self, meta_id):
        return [h for m, h in reversed(self.filas) if m == meta_id]


class VentaDAOMemoria(VentaDAO):

    def __init__(self, ventas=None):
        self.ventas = ventas or {}       # {(anio, mes): {tienda_id: VentaMesDTO}}

    def ventas_del_mes(self, anio, mes):
        return dict(self.ventas.get((anio, mes), {}))


def tiendas_de_ejemplo():
    return [TiendaDTO(1, "S-01", "Tienda Norte Ejemplo", "Bogotá"), TiendaDTO(2, "S-02", "Tienda Sur Ejemplo", "Bogotá"),
            TiendaDTO(3, "S-03", "Tienda Centro Ejemplo", "Medellín")]


def ventas_de_ejemplo(anio, mes):
    return {(anio, mes): {1: VentaMesDTO(9_000_000, 20), 2: VentaMesDTO(12_000_000, 20)}}
