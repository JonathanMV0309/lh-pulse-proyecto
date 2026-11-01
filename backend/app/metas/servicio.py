"""FACADE: una sola puerta para todo lo de metas.

Problema: consultar o guardar una meta involucra varias piezas: cuatro DAO, la cadena de
validaciones, el semáforo, el builder del resumen y los observadores. Si la API (o una pantalla, o
un comando) tuviera que coordinarlas, repetiría esa coordinación y quedaría atada a todas ellas.

ServicioMetas ofrece pocas operaciones simples (listar, obtener, crear, ajustar, eliminar, historial)
y por dentro orquesta las piezas. La API solo traduce HTTP <-> servicio. Complejidad: si la fachada
crece demasiado se vuelve una «clase dios»; por eso solo coordina y deja cada regla en su pieza.
"""
from datetime import date

from app.metas.builder import ResumenTiendaBuilder
from app.metas.eventos import EventoMeta, HistorialObserver, PublicadorEventosMeta, RegistroLogObserver
from app.metas.fabrica import fabrica_configurada
from app.metas.semaforo import estrategia_configurada
from app.metas.validaciones import ErrorValidacion, cadena_para_ajustar, cadena_para_crear


class ServicioMetas:

    def __init__(self, fabrica=None, estrategia=None, hoy=None):
        fabrica = fabrica or fabrica_configurada()
        self.tiendas = fabrica.crear_tienda_dao()
        self.metas = fabrica.crear_meta_dao()
        self.historial = fabrica.crear_historial_dao()
        self.ventas = fabrica.crear_venta_dao()
        self.estrategia = estrategia or estrategia_configurada()
        self.hoy = hoy
        self.eventos = PublicadorEventosMeta()
        self.eventos.suscribir(HistorialObserver(self.historial)).suscribir(RegistroLogObserver())

    # ---------- Consultas (HU-05) ----------
    def listar_tiendas(self):
        return self.tiendas.listar_activas()

    def resumen_del_mes(self, anio, mes):
        """Todas las tiendas activas con su meta, venta, cumplimiento y semáforo; las peores primero."""
        if not 1 <= mes <= 12:
            raise ErrorValidacion("El mes debe estar entre 1 y 12.", "mes")
        metas = {m.tienda_id: m for m in self.metas.listar_periodo(anio, mes)}
        ventas = self.ventas.ventas_del_mes(anio, mes)
        filas = [ResumenTiendaBuilder().para_tienda(t).en_periodo(anio, mes).con_meta(metas.get(t.id))
                 .con_venta(ventas.get(t.id)).calificado_con(self.estrategia).construir()
                 for t in self.tiendas.listar_activas()]
        orden = {"rojo": 0, "amarillo": 1, "verde": 2, "gris": 3}
        filas.sort(key=lambda f: (orden[f.semaforo], f.cumplimiento_pct if f.cumplimiento_pct is not None else 0, f.tienda_codigo))
        return filas

    def obtener(self, meta_id):
        meta = self.metas.obtener(meta_id)
        if meta is None:
            raise ErrorValidacion("La meta no existe.", None, 404)
        return meta

    def historial_de(self, meta_id):
        return self.historial.listar(meta_id)

    # ---------- Cambios (HU-06) ----------
    def crear(self, entrada, usuario):
        cadena_para_crear(self.tiendas, self.metas).validar(entrada, {"hoy": self.hoy or date.today()})
        meta = self.metas.crear(entrada, usuario)
        self.eventos.publicar(EventoMeta("creada", meta, None, usuario))
        return meta

    def ajustar(self, meta_id, entrada, usuario):
        anterior = self.obtener(meta_id)
        cadena_para_ajustar().validar(entrada, {"ajuste": True})
        meta = self.metas.actualizar(meta_id, entrada, usuario)
        if anterior.valor != meta.valor:
            self.eventos.publicar(EventoMeta("ajustada", meta, anterior.valor, usuario))
        return meta

    def eliminar(self, meta_id, usuario):
        meta = self.obtener(meta_id)
        self.metas.eliminar(meta_id)
        self.eventos.publicar(EventoMeta("eliminada", meta, meta.valor, usuario))
        return meta
