"""Evidencias del Sprint 2: capturas de las pantallas, de la API y de Docker, con la app corriendo en Docker.

Uso (desde la raíz del repositorio, con `docker compose up -d` ya arriba):
    python herramientas/capturas_sprint2.py

El correo y la clave del administrador de ejemplo se leen del .env local; no se imprimen ni se guardan.
Necesita: pip install playwright python-dotenv  (usa Microsoft Edge instalado en Windows).
"""
import html
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from dotenv import dotenv_values
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "docs" / "sprint2" / "capturas"
SALIDA.mkdir(parents=True, exist_ok=True)
ENV = dotenv_values(RAIZ / ".env")
URL = f"http://127.0.0.1:{ENV.get('API_PUERTO') or 5075}"
HOY = date.today()

TERMINAL = """<style>body{margin:0;background:#0c0c0c}.v{border:1px solid #333;font:13px/1.45 Consolas,'Cascadia Mono',monospace;color:#ccc}
.b{background:#1f1f1f;color:#bbb;padding:6px 12px;font:12px 'Segoe UI',sans-serif}pre{margin:0;padding:12px 16px;white-space:pre-wrap;word-break:break-word}
.c{color:#61d6d6}.ok{color:#16c60c}</style>"""

API = """<style>body{margin:0;background:#F5F0E8;font:14px Inter,'Segoe UI',sans-serif;color:#2D2A26;padding:18px}
h1{font-size:18px;margin:0 0 12px}.p{background:#fff;border:1px solid rgba(139,125,107,.3);border-radius:12px;margin-bottom:12px;overflow:hidden}
.c{display:flex;gap:10px;align-items:center;padding:10px 14px;background:#FDFBF7;border-bottom:1px solid rgba(139,125,107,.2);font-weight:700}
.m{padding:2px 8px;border-radius:6px;color:#fff;font-size:12px}.GET{background:#1D4ED8}.POST{background:#1F5E3F}.PUT{background:#7A5A12}.DELETE{background:#9F1D1D}
.s{margin-left:auto;padding:2px 10px;border-radius:999px;font-size:12px}.s2{background:#D9EFE2;color:#1F5E3F}.s4{background:#FBE3DF;color:#9F1D1D}
.d{padding:4px 14px;color:#6B6259;font-size:12.5px}pre{margin:0;padding:10px 14px;font:12.5px/1.45 Consolas,monospace;white-space:pre-wrap;max-height:260px;overflow:hidden}</style>"""


def terminal(nombre, titulo, comandos):
    bloques = []
    for cmd in comandos:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + cmd], cwd=RAIZ,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        bloques.append(f'<span class="c">PS {html.escape(str(RAIZ))}&gt; {html.escape(cmd)}</span>\n{html.escape((r.stdout + r.stderr).rstrip())}\n')
    return nombre, f'{TERMINAL}<div class="v"><div class="b">{html.escape(titulo)}</div><pre>{"".join(bloques)}</pre></div>'


with sync_playwright() as p:
    navegador = p.chromium.launch(channel="msedge")
    contexto = navegador.new_context(viewport={"width": 1440, "height": 900}, locale="es-CO")
    pagina = contexto.new_page()

    def foto(nombre, completa=False):
        pagina.wait_for_timeout(900)
        pagina.screenshot(path=SALIDA / nombre, full_page=completa)
        print("captura", nombre)

    # Sin sesión: la API responde 401 en JSON
    sin_sesion = pagina.request.get(f"{URL}/api/v1/metas")
    pruebas_api = [("GET", "/api/v1/metas", "Sin iniciar sesión", sin_sesion.status, sin_sesion.json())]

    r = pagina.request.post(f"{URL}/api/auth/login", data={"correo": ENV["SEMILLA_ADMIN_CORREO"], "password": ENV["SEMILLA_ADMIN_CLAVE"]})
    assert r.ok, "No se pudo iniciar sesión con el administrador de ejemplo del .env"

    # Para que la demostración se pueda repetir: la S-09 empieza sin meta este mes
    for f in pagina.request.get(f"{URL}/api/v1/metas?anio={HOY.year}&mes={HOY.month}").json()["tiendas"]:
        if f["tienda_codigo"] == "S-09" and f["meta_id"]:
            pagina.request.delete(f"{URL}/api/v1/metas/{f['meta_id']}")
    tiendas = {t["codigo"]: t["id"] for t in pagina.request.get(f"{URL}/api/v1/tiendas").json()["tiendas"]}

    # HU-05: consulta
    pagina.goto(f"{URL}/metas-tienda/?anio={HOY.year}&mes={HOY.month}", wait_until="networkidle")
    foto("app_01_consulta_metas.png")

    # HU-06: formulario vacío con la tienda elegida desde «Poner meta»
    pagina.goto(f"{URL}/metas-tienda/nueva?tienda={tiendas['S-09']}&anio={HOY.year}&mes={HOY.month}", wait_until="networkidle")
    foto("app_02_nueva_meta.png")
    pagina.click("#mtGuardar")                                      # sin valor: error de validación
    foto("app_03_validacion_valor.png")
    pagina.select_option("#tienda_id", str(tiendas["S-01"]))         # la S-01 ya tiene meta: 409
    pagina.fill("#valor", "50000000")
    pagina.click("#mtGuardar")
    foto("app_04_meta_duplicada.png")
    pagina.select_option("#tienda_id", str(tiendas["S-09"]))
    pagina.fill("#valor", "")
    pagina.type("#valor", "58000000")
    pagina.fill("#nota", "Meta de noviembre acordada con la supervisora")
    pagina.click("#mtGuardar")
    pagina.wait_for_url("**/metas-tienda/?*")
    pagina.wait_for_load_state("networkidle")
    foto("app_05_meta_creada.png")

    # HU-06: ajustar la meta recién creada
    meta_s09 = next(f for f in pagina.request.get(f"{URL}/api/v1/metas?anio={HOY.year}&mes={HOY.month}").json()["tiendas"] if f["tienda_codigo"] == "S-09")
    pagina.goto(f"{URL}/metas-tienda/{meta_s09['meta_id']}/editar", wait_until="networkidle")
    foto("app_06_ajustar_meta.png")
    pagina.fill("#valor", "")
    pagina.type("#valor", "61500000")
    pagina.fill("#nota", "Se sube por la temporada de fin de año")
    pagina.click("#mtGuardar")
    pagina.wait_for_url("**/metas-tienda/?*")
    pagina.wait_for_load_state("networkidle")
    foto("app_07_meta_ajustada.png")

    # HU-07: historial
    pagina.click(f"[data-hist='{meta_s09['meta_id']}']")
    pagina.wait_for_selector("#mtHistCuerpo .mt-linea")
    foto("app_08_historial.png")

    # Pruebas de la API (como en Postman / Thunder Client), con respuestas reales
    def probar(metodo, ruta, descripcion, cuerpo=None):
        r = pagina.request.fetch(f"{URL}{ruta}", method=metodo, data=cuerpo)
        pruebas_api.append((metodo, ruta, descripcion, r.status, r.json()))

    probar("GET", f"/api/v1/metas?anio={HOY.year}&mes={HOY.month}", "Resumen del mes (HU-05)")
    probar("POST", "/api/v1/metas", "Crear con datos válidos (HU-06)", {"tienda_id": tiendas["S-10"], "anio": HOY.year, "mes": HOY.month, "valor": 47000000, "nota": "Prueba de la API"})
    nueva = pruebas_api[-1][4].get("meta", {}).get("id")
    probar("POST", "/api/v1/metas", "Crear sin valor: validación", {"tienda_id": tiendas["S-10"], "anio": HOY.year, "mes": HOY.month})
    probar("POST", "/api/v1/metas", "Crear repetida: conflicto", {"tienda_id": tiendas["S-10"], "anio": HOY.year, "mes": HOY.month, "valor": 1000})
    probar("PUT", f"/api/v1/metas/{nueva}", "Ajustar (HU-06)", {"valor": 49000000})
    probar("GET", f"/api/v1/metas/{nueva}/historial", "Historial (HU-07)")
    probar("DELETE", f"/api/v1/metas/{nueva}", "Eliminar")
    probar("GET", f"/api/v1/metas/{nueva}", "Consultar la eliminada")

    def tarjeta(m, ruta, desc, estado, cuerpo):
        if isinstance(cuerpo, dict) and "tiendas" in cuerpo and len(cuerpo["tiendas"]) > 2:
            cuerpo = dict(cuerpo, tiendas=cuerpo["tiendas"][:2] + [f"… y {len(cuerpo['tiendas']) - 2} tiendas más"])
        return (f'<div class="p"><div class="c"><span class="m {m}">{m}</span>{html.escape(ruta)}<span class="s s{str(estado)[0]}">{estado}</span></div>'
                f'<div class="d">{html.escape(desc)}</div><pre>{html.escape(json.dumps(cuerpo, ensure_ascii=False, indent=2))}</pre></div>')

    for nombre, desde, hasta in [("api_01_consultas.png", 0, 2), ("api_02_crear_y_validar.png", 2, 5), ("api_03_ajustar_historial_eliminar.png", 5, 9)]:
        pagina.set_content(f'{API}<h1>Pruebas de la API de metas · {URL}</h1>' + "".join(tarjeta(*x) for x in pruebas_api[desde:hasta]))
        foto(nombre, completa=True)

    # Docker y pruebas automáticas
    capturas = [
        terminal("docker_01_contenedores.png", "Windows PowerShell · docker compose",
                 ["docker compose ps", "docker volume ls --filter name=lhpulse", "docker compose logs api --no-log-prefix | Select-String -Pattern 'Listo|siembra|Listening'"]),
        terminal("pruebas_01_pytest.png", "Windows PowerShell · pruebas automáticas",
                 [f"cd backend; & '{sys.executable}' -m pytest tests/proyecto -v -p no:cacheprovider -W ignore::DeprecationWarning"]),
    ]
    pagina.set_viewport_size({"width": 1180, "height": 600})
    for nombre, contenido in capturas:
        pagina.set_content(contenido)
        foto(nombre, completa=True)
    navegador.close()
