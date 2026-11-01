"""Builder, Decorator, Facade, Strategy, Observer y Chain of Responsibility, sin base de datos."""
from datetime import date

import pytest

from app.metas.builder import ResumenTiendaBuilder
from app.metas.dao.memoria_dao import TiendaDAOMemoria, tiendas_de_ejemplo, ventas_de_ejemplo
from app.metas.decoradores import TiendaDAOConCache
from app.metas.dto import MetaEntradaDTO, VentaMesDTO
from app.metas.eventos import EventoMeta, ObservadorMeta, PublicadorEventosMeta
from app.metas.fabrica import FabricaMemoria, FabricaSQLAlchemy
from app.metas.semaforo import SemaforoMensual, SemaforoProporcional, estrategia_configurada
from app.metas.servicio import ServicioMetas
from app.metas.validaciones import ErrorValidacion

HOY = date(2026, 11, 20)


def servicio():
    return ServicioMetas(FabricaMemoria(ventas=ventas_de_ejemplo(2026, 11)), SemaforoProporcional(), hoy=HOY)


def entrada(**kw):
    datos = {"tienda_id": 1, "anio": 2026, "mes": 11, "valor": 30_000_000}
    datos.update(kw)
    return MetaEntradaDTO.desde_json(datos)


# ---------- Creacional ----------
def test_builder_sin_meta_y_con_meta():
    t = tiendas_de_ejemplo()[0]
    sin = ResumenTiendaBuilder().para_tienda(t).en_periodo(2026, 11).calificado_con(SemaforoMensual()).construir()
    assert (sin.estado, sin.semaforo, sin.cumplimiento_pct) == ("sin_meta", "gris", None)
    from app.metas.dto import MetaDTO
    con = (ResumenTiendaBuilder().calificado_con(SemaforoMensual()).con_venta(VentaMesDTO(9_500_000, 20))
           .con_meta(MetaDTO(7, 1, 2026, 11, 10_000_000)).para_tienda(t).en_periodo(2026, 11).construir())
    assert (con.meta_id, con.cumplimiento_pct, con.semaforo) == (7, 95.0, "amarillo")
    with pytest.raises(ValueError):
        ResumenTiendaBuilder().para_tienda(t).construir()


# ---------- Estructurales ----------
def test_decorator_cache_evita_consultas_repetidas():
    reloj = [0.0]
    real = TiendaDAOMemoria(tiendas_de_ejemplo())
    cache = TiendaDAOConCache(real, segundos=60, reloj=lambda: reloj[0])
    for _ in range(5):
        cache.listar_activas()
        cache.obtener(2)
    assert real.consultas == 1
    reloj[0] = 61
    cache.listar_activas()
    assert real.consultas == 2


def test_facade_flujo_completo():
    s = servicio()
    meta = s.crear(entrada(), "Ana")
    assert meta.tienda_codigo == "S-01"
    s.ajustar(meta.id, MetaEntradaDTO.desde_json({"valor": 25_000_000, "nota": "ajuste"}), "Bea")
    resumen = {f.tienda_codigo: f for f in s.resumen_del_mes(2026, 11)}
    assert resumen["S-01"].meta == 25_000_000 and resumen["S-03"].estado == "sin_meta"
    s.eliminar(meta.id, "Ana")
    assert [h.accion for h in s.historial_de(meta.id)] == ["eliminada", "ajustada", "creada"]


def test_fabrica_sqlalchemy_envuelve_tiendas_con_cache():
    assert isinstance(FabricaSQLAlchemy().crear_tienda_dao(), TiendaDAOConCache)


# ---------- Comportamiento ----------
def test_strategy_proporcional_contra_mensual():
    # 20 de 30 días: la meta al corte es 2/3 de la meta
    p = SemaforoProporcional().evaluar(30_000_000, 20_000_000, 20, 2026, 11)
    m = SemaforoMensual().evaluar(30_000_000, 20_000_000, 20, 2026, 11)
    assert (p.cumplimiento_pct, p.semaforo) == (100.0, "verde")
    assert (m.cumplimiento_pct, m.semaforo) == (66.7, "rojo")


def test_strategy_configurada(monkeypatch):
    monkeypatch.setenv("METAS_SEMAFORO", "mensual")
    assert isinstance(estrategia_configurada(), SemaforoMensual)


def test_observer_avisa_a_todos_aunque_uno_falle():
    recibidos = []

    class Roto(ObservadorMeta):
        def notificar(self, evento):
            raise RuntimeError("falla")

    class Anota(ObservadorMeta):
        def notificar(self, evento):
            recibidos.append(evento.accion)

    p = PublicadorEventosMeta().suscribir(Roto()).suscribir(Anota())
    p.publicar(EventoMeta("creada", None, None, "Ana"))
    assert recibidos == ["creada"]


@pytest.mark.parametrize("datos, campo, http", [
    ({"valor": None}, "valor", 400),
    ({"valor": "abc"}, "valor", 400),
    ({"mes": 13}, "mes", 400),
    ({"anio": 2019}, "anio", 400),
    ({"mes": 10}, "mes", 400),                  # mes que ya pasó
    ({"valor": -5}, "valor", 400),
    ({"valor": 99_000_000_000}, "valor", 400),
    ({"tienda_id": 77}, "tienda_id", 404),
])
def test_chain_corta_en_el_primer_error(datos, campo, http):
    with pytest.raises(ErrorValidacion) as e:
        servicio().crear(entrada(**datos), "Ana")
    assert (e.value.campo, e.value.estado_http) == (campo, http)


def test_chain_no_permite_duplicado():
    s = servicio()
    s.crear(entrada(), "Ana")
    with pytest.raises(ErrorValidacion) as e:
        s.crear(entrada(valor=1_000), "Ana")
    assert e.value.estado_http == 409
