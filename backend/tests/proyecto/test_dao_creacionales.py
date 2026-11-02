"""DAO, DTO, Singleton, Abstract Factory y Adapter, sin base de datos (familia de DAO en memoria)."""
import pytest

from app.metas.configuracion import ConfiguracionMetas
from app.metas.dao.memoria_dao import tiendas_de_ejemplo
from app.metas.dto import MetaEntradaDTO
from app.metas.fabrica import FabricaMemoria, fabrica_configurada


def test_singleton_una_sola_configuracion(monkeypatch):
    monkeypatch.setenv("METAS_SEMAFORO", "mensual")
    a, b = ConfiguracionMetas(), ConfiguracionMetas()
    assert a is b and a.semaforo == "mensual"
    monkeypatch.setenv("METAS_SEMAFORO", "proporcional")
    assert ConfiguracionMetas().semaforo == "mensual"       # no se vuelve a leer el entorno


def test_abstract_factory_elige_la_familia(monkeypatch):
    monkeypatch.setenv("METAS_ORIGEN_DATOS", "memoria")
    f = fabrica_configurada()
    assert isinstance(f, FabricaMemoria)
    assert f.crear_meta_dao().tiendas_dao is f.crear_tienda_dao()   # la misma familia comparte datos
    ConfiguracionMetas.reiniciar()
    monkeypatch.setenv("METAS_ORIGEN_DATOS", "otra")
    with pytest.raises(ValueError):
        fabrica_configurada()


def test_dao_en_memoria_crud_y_copias():
    f = FabricaMemoria(tiendas=tiendas_de_ejemplo())
    metas = f.crear_meta_dao()
    m = metas.crear(MetaEntradaDTO.desde_json({"tienda_id": 2, "anio": 2026, "mes": 11, "valor": 10}), "Ana")
    assert metas.buscar(2, 2026, 11).id == m.id and m.tienda_codigo == "S-02"
    copia = metas.obtener(m.id)
    copia.valor = 999                                # cambiar lo recibido no cambia lo guardado
    assert metas.obtener(m.id).valor == 10
    metas.actualizar(m.id, MetaEntradaDTO.desde_json({"valor": 20}), "Bea")
    assert metas.obtener(m.id).valor == 20 and metas.obtener(m.id).actualizado_por == "Bea"
    assert metas.eliminar(m.id) and metas.obtener(m.id) is None


def test_dto_no_expone_campos_internos():
    d = MetaEntradaDTO.desde_json({"tienda_id": "1", "anio": "2026", "mes": "11", "valor": "45.000.000", "id": 99, "actualizado_por": "x"})
    assert (d.tienda_id, d.valor) == (1, 45_000_000)
    assert not hasattr(d, "id") and not hasattr(d, "actualizado_por")
    assert MetaEntradaDTO.desde_json("no es un objeto").valor is None
