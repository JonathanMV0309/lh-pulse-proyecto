"""Módulo 2: permisos (app/utils/permissions.py) y ranking de asesoras (app/routes/ranking.py)."""
import pytest

from app.routes import ranking

from .conftest import ANIO, CORTE, MES, iniciar_sesion


# ---------- Decorador admin_required ----------

def test_admin_required_sin_sesion_redirige_al_login(client):
    respuesta = client.get("/solo-admin")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/")


def test_admin_required_permite_al_administrador(client):
    iniciar_sesion(client, 1, "Administrador")

    respuesta = client.get("/solo-admin")

    assert respuesta.status_code == 200
    assert b"contenido de administrador" in respuesta.data


def test_admin_required_rechaza_al_usuario_tienda(client):
    iniciar_sesion(client, 2, "TIENDA")

    respuesta = client.get("/solo-admin")

    assert respuesta.status_code == 302


def test_admin_required_acepta_el_rol_escrito_en_mayusculas(client):
    """Antes: /api/auth/register y el ranking aceptaban 'ADMINISTRADOR', pero admin_required no."""
    iniciar_sesion(client, 5, "ADMINISTRADOR")

    respuesta = client.get("/solo-admin")

    assert respuesta.status_code == 200


# ---------- Ranking de desempeño: permisos ----------

@pytest.fixture
def contexto_ranking(monkeypatch):
    """Captura lo que la ruta le pasa a la plantilla (la plantilla completa necesita toda la app)."""
    capturado = {}

    def falso_render(plantilla, **contexto):
        capturado.update(contexto, plantilla=plantilla)
        return "ok"

    monkeypatch.setattr(ranking, "render_template", falso_render)
    # Metas inventadas por asesora: Ana 5 M, Carla 4 M, Bea sin meta.
    monkeypatch.setattr(ranking, "obtener_meta_tienda", lambda store_id, anio, mes: 1)
    metas = {1: [{"advisor_id": 1, "meta": 5_000_000}], 2: [{"advisor_id": 3, "meta": 4_000_000}]}
    monkeypatch.setattr(
        ranking, "calcular_metas_asesoras",
        lambda store_id, anio, mes, meta_tienda: {"asesoras": metas.get(store_id, [])},
    )
    return capturado


def test_ranking_sin_sesion_responde_401(client):
    assert client.get("/ranking/desempeno/").status_code == 401


def test_ranking_rechaza_rol_sin_permiso(client):
    iniciar_sesion(client, 3, "ASESORA")

    assert client.get("/ranking/desempeno/").status_code == 403


def test_ranking_rechaza_usuario_inactivo(client):
    iniciar_sesion(client, 4, "Administrador")

    assert client.get("/ranking/desempeno/").status_code == 403


def test_ranking_de_tiendas_para_administrador(client, contexto_ranking):
    iniciar_sesion(client, 1, "Administrador")

    respuesta = client.get(f"/ranking/desempeno/?anio={ANIO}&mes={MES}&dia_corte={CORTE}")

    assert respuesta.status_code == 200
    tiendas = contexto_ranking["ranking_tiendas"]
    # Sin la fila TOTAL y sin S-24 (cerrada desde agosto de 2026); ordenado por cumplimiento.
    assert [t["codigo"] for t in tiendas] == ["S-02", "S-01"]
    assert [t["posicion"] for t in tiendas] == [1, 2]
    assert tiendas[0]["meta_corte"] == pytest.approx(10_000_000)
    assert contexto_ranking["es_tienda"] is False
    assert contexto_ranking["mi_store_id"] is None


def test_ranking_de_asesoras_ordena_y_deja_sin_puesto_a_quien_no_tiene_meta(client, contexto_ranking):
    iniciar_sesion(client, 1, "Administrador")

    client.get(f"/ranking/desempeno/?anio={ANIO}&mes={MES}&dia_corte={CORTE}")

    asesoras = contexto_ranking["ranking_asesoras"]
    assert [a["asesora"] for a in asesoras] == ["Carla Ejemplo", "Ana Ejemplo", "Bea Ejemplo"]
    assert [a["posicion"] for a in asesoras] == [1, 2, None]
    carla = asesoras[0]
    assert carla["ticket"] == pytest.approx(100_000)
    assert carla["upt"] == pytest.approx(3)
    assert carla["cumplimiento"] == pytest.approx(5_000_000 / carla["meta_corte"])
    assert asesoras[2]["sin_meta"] is True and asesoras[2]["cumplimiento"] == 0


def test_ranking_de_asesoras_sin_facturas_no_divide_por_cero(app, client, contexto_ranking):
    from app.extensions import db
    from app.models import AdvisorPerformance

    AdvisorPerformance.query.filter_by(advisor_id=3).update({"facturas": 0, "unidades": 0})
    db.session.commit()
    iniciar_sesion(client, 1, "Administrador")

    client.get(f"/ranking/desempeno/?anio={ANIO}&mes={MES}&dia_corte={CORTE}")

    carla = next(a for a in contexto_ranking["ranking_asesoras"] if a["asesora"] == "Carla Ejemplo")
    assert carla["ticket"] == 0 and carla["upt"] == 0


def test_ranking_para_usuario_tienda_marca_su_tienda(client, contexto_ranking):
    iniciar_sesion(client, 2, "TIENDA")

    respuesta = client.get(f"/ranking/desempeno/?anio={ANIO}&mes={MES}&dia_corte={CORTE}")

    assert respuesta.status_code == 200
    assert contexto_ranking["es_tienda"] is True
    assert contexto_ranking["mi_store_id"] == 1


def test_ranking_filtra_por_tienda_y_busqueda(client, contexto_ranking):
    iniciar_sesion(client, 1, "Administrador")

    client.get(f"/ranking/desempeno/?anio={ANIO}&mes={MES}&dia_corte={CORTE}&store_id=1&buscar=ana")

    assert [a["asesora"] for a in contexto_ranking["ranking_asesoras"]] == ["Ana Ejemplo"]


def test_ranking_si_falla_el_calculo_de_metas_la_tienda_queda_sin_meta(client, contexto_ranking, monkeypatch):
    def meta_que_falla(store_id, anio, mes):
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr(ranking, "obtener_meta_tienda", meta_que_falla)
    iniciar_sesion(client, 1, "Administrador")

    respuesta = client.get(f"/ranking/desempeno/?anio={ANIO}&mes={MES}&dia_corte={CORTE}")

    assert respuesta.status_code == 200
    assert all(a["sin_meta"] and a["posicion"] is None for a in contexto_ranking["ranking_asesoras"])
