"""Pantallas de metas: solo la administración las abre, y cada una pide sus datos a la API."""
from pathlib import Path

PLANTILLAS = Path(__file__).resolve().parents[2] / "app" / "templates" / "metas_tienda"


def test_pantallas_solo_para_la_administracion(app, tienda):
    assert app.test_client().get("/metas-tienda/").status_code == 302          # sin sesión
    assert tienda.get("/metas-tienda/").status_code == 302                      # rol tienda
    assert tienda.get("/metas-tienda/nueva").status_code == 302
    assert {"metas_paginas.consulta", "metas_paginas.nueva", "metas_paginas.editar"} <= set(app.view_functions)


def test_las_pantallas_usan_la_api_y_no_datos_simulados():
    consulta = (PLANTILLAS / "consulta.html").read_text(encoding="utf-8")
    formulario = (PLANTILLAS / "formulario.html").read_text(encoding="utf-8")
    assert "/api/v1/metas?anio=" in consulta and "/historial" in consulta
    assert "/api/v1/tiendas" in formulario and "method: META_ID ? 'PUT' : 'POST'" in formulario
    assert "method: 'DELETE'" in formulario
