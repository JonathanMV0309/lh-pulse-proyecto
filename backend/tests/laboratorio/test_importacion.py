"""Módulo 3: carga del Excel de ventas (app/routes/import_excel.py)."""
import io

import pytest

from app.routes import import_excel

from .conftest import iniciar_sesion, mensajes_flash


@pytest.fixture
def importador(monkeypatch, tmp_path):
    """Trabaja en una carpeta temporal y reemplaza el procesamiento real del Excel."""
    trabajo = tmp_path / "servidor" / "backend"
    trabajo.mkdir(parents=True)
    monkeypatch.chdir(trabajo)
    llamadas = []

    def importar_falso(ruta):
        llamadas.append(ruta)
        return 42

    monkeypatch.setattr(import_excel, "importar_excel_completo", importar_falso)
    return {"llamadas": llamadas, "trabajo": trabajo, "raiz": tmp_path}


def subir(client, nombre, contenido=b"datos de prueba"):
    return client.post(
        "/import/excel",
        data={"archivo": (io.BytesIO(contenido), nombre)},
        content_type="multipart/form-data",
    )


# ---------- Comportamiento normal ----------

def test_importacion_valida_guarda_en_uploads_y_procesa(client, importador):
    iniciar_sesion(client, 1, "Administrador")

    respuesta = subir(client, "VENTAS_OCT_2026.xlsx")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/dashboard")
    assert (importador["trabajo"] / "uploads" / "VENTAS_OCT_2026.xlsx").exists()
    assert len(importador["llamadas"]) == 1
    assert "Se cargaron 42 registros" in mensajes_flash(client)[0]


def test_importacion_acepta_xls(client, importador):
    iniciar_sesion(client, 1, "Administrador")

    subir(client, "ventas.xls")

    assert len(importador["llamadas"]) == 1


# ---------- Comportamiento de error ----------

def test_importacion_requiere_administrador(client, importador):
    iniciar_sesion(client, 2, "TIENDA")

    respuesta = subir(client, "ventas.xlsx")

    assert respuesta.status_code == 302
    assert importador["llamadas"] == []


def test_importacion_sin_archivo_avisa(client, importador):
    iniciar_sesion(client, 1, "Administrador")

    respuesta = client.post("/import/excel", data={}, content_type="multipart/form-data")

    assert respuesta.status_code == 302
    assert mensajes_flash(client) == ["No se recibió ningún archivo."]


def test_importacion_no_escribe_fuera_de_uploads(client, importador):
    """Antes: el nombre '../../malicioso.xlsx' se usaba tal cual y el archivo quedaba fuera de uploads/."""
    iniciar_sesion(client, 1, "Administrador")

    subir(client, "../../malicioso.xlsx")

    carpeta_uploads = (importador["trabajo"] / "uploads").resolve()
    escritos = [p.resolve() for p in importador["raiz"].rglob("malicioso.xlsx")]
    assert escritos, "el archivo debía guardarse (con un nombre seguro)"
    assert all(p.parent == carpeta_uploads for p in escritos), f"Se escribió fuera de uploads/: {escritos}"


@pytest.mark.parametrize("nombre", ["script.py", "virus.exe", "ventas.csv", "sin_extension"])
def test_importacion_rechaza_extensiones_no_permitidas(client, importador, nombre):
    """Antes: cualquier archivo se guardaba en el servidor y se intentaba procesar."""
    iniciar_sesion(client, 1, "Administrador")

    respuesta = subir(client, nombre)

    assert respuesta.status_code == 302
    assert importador["llamadas"] == []
    assert not (importador["trabajo"] / "uploads" / nombre).exists()


def test_importacion_con_error_de_proceso_avisa_y_vuelve(client, importador, monkeypatch):
    def importar_con_error(ruta):
        raise ValueError("La hoja CUMPL no tiene la columna TIENDA")

    monkeypatch.setattr(import_excel, "importar_excel_completo", importar_con_error)
    iniciar_sesion(client, 1, "Administrador")

    respuesta = subir(client, "ventas.xlsx")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/import/")
    assert mensajes_flash(client) == ["La hoja CUMPL no tiene la columna TIENDA"]
