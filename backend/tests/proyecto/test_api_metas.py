"""API de metas contra una base SQLite en memoria (DAO SQLAlchemy + adaptador de compliance)."""
from tests.proyecto.conftest import HOY


def test_api_pide_sesion_y_rol(app, tienda):
    assert app.test_client().get("/api/v1/metas").status_code == 401
    r = tienda.get("/api/v1/metas")
    assert r.status_code == 403 and r.get_json()["ok"] is False


def test_resumen_usa_el_ultimo_informe_de_ventas(admin):
    j = admin.get(f"/api/v1/metas?anio={HOY.year}&mes={HOY.month}").get_json()
    filas = {f["tienda_codigo"]: f for f in j["tiendas"]}
    assert set(filas) == {"S-01", "S-02"}                     # la inactiva no sale
    assert filas["S-01"]["venta"] == 9_000_000 and filas["S-01"]["dia_corte"] == 20
    assert filas["S-02"]["estado"] == "sin_meta" and filas["S-02"]["semaforo"] == "gris"


def test_crear_ajustar_historial_y_eliminar(admin):
    r = admin.post("/api/v1/metas", json={"tienda_id": 2, "anio": HOY.year, "mes": HOY.month, "valor": 30_000_000, "nota": "nueva"})
    assert r.status_code == 201, r.get_json()
    meta_id = r.get_json()["meta"]["id"]
    r = admin.put(f"/api/v1/metas/{meta_id}", json={"valor": 32_000_000})
    assert r.status_code == 200 and r.get_json()["meta"]["valor"] == 32_000_000
    hist = admin.get(f"/api/v1/metas/{meta_id}/historial").get_json()["historial"]
    assert [h["accion"] for h in hist] == ["ajustada", "creada"] and hist[0]["valor_anterior"] == 30_000_000
    assert admin.delete(f"/api/v1/metas/{meta_id}").status_code == 200
    assert admin.get(f"/api/v1/metas/{meta_id}").status_code == 404


def test_errores_de_validacion_en_json(admin):
    r = admin.post("/api/v1/metas", json={"tienda_id": 1, "anio": HOY.year, "mes": HOY.month, "valor": 5})
    assert r.status_code == 409 and r.get_json()["campo"] == "mes"           # ya tiene meta ese mes
    r = admin.post("/api/v1/metas", json={"tienda_id": 3, "anio": HOY.year, "mes": HOY.month, "valor": 5})
    assert r.status_code == 404 and r.get_json()["campo"] == "tienda_id"     # tienda inactiva
    r = admin.post("/api/v1/metas", data="no es json", content_type="text/plain")
    assert r.status_code == 400
    assert admin.get("/api/v1/metas?mes=abc").status_code == 400
    assert admin.put("/api/v1/metas/999", json={"valor": 1}).status_code == 404

