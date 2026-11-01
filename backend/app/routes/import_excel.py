from flask import (
    Blueprint,
    request,
    render_template,
    redirect,
    url_for,
    flash,
    session
)

import os

from werkzeug.utils import secure_filename

from app.services.import_service import importar_excel_completo
from app.utils.permissions import admin_required
from app.models.archivo_importado import ArchivoImportado
from app.extensions import db


import_excel_bp = Blueprint(
    "import_excel",
    __name__,
    url_prefix="/import"
)


UPLOAD_FOLDER = "uploads"

# Mismas extensiones que acepta el selector de archivos de importar.html.
EXTENSIONES_PERMITIDAS = {".xlsx", ".xls"}


def _nombre_seguro_excel(nombre_original):
    """Nombre limpio para guardar el archivo dentro de UPLOAD_FOLDER, o None si no es un Excel.

    secure_filename quita rutas y caracteres peligrosos ("../../x.xlsx" -> "x.xlsx"),
    así el archivo nunca se escribe fuera de la carpeta de cargas.
    """
    nombre = secure_filename(nombre_original or "")
    if os.path.splitext(nombre)[1].lower() not in EXTENSIONES_PERMITIDAS:
        return None
    return nombre


# ==========================================================
# PÁGINA DE IMPORTAR
# ==========================================================

@import_excel_bp.route("/", methods=["GET"])
@admin_required
def pagina_importar():
    return render_template("importar.html")


# ==========================================================
# HISTORIAL DE ARCHIVOS IMPORTADOS
# ==========================================================

@import_excel_bp.route("/historial", methods=["GET"])
@admin_required
def historial_importaciones():
    archivos = (
        ArchivoImportado.query
        .order_by(ArchivoImportado.fecha_carga.desc())
        .all()
    )
    return render_template(
        "importar_historial.html",
        archivos=archivos
    )


# ==========================================================
# ELIMINAR ARCHIVO IMPORTADO
# ==========================================================

@import_excel_bp.route("/historial/<int:archivo_id>/eliminar", methods=["POST"])
@admin_required
def eliminar_archivo(archivo_id):
    archivo = ArchivoImportado.query.get_or_404(archivo_id)

    # Guardar datos antes de eliminar
    ruta_archivo = archivo.ruta
    nombre_archivo = archivo.nombre_archivo

    try:
        # Eliminar registro de la base de datos
        db.session.delete(archivo)
        db.session.commit()

        # Eliminar archivo físico si existe
        if ruta_archivo and os.path.exists(ruta_archivo):
            try:
                os.remove(ruta_archivo)
            except OSError as e:
                # No interrumpir si falla el borrado físico
                print(f"Error al eliminar archivo físico: {e}")

        flash(
            f"El archivo '{nombre_archivo}' fue eliminado del historial.",
            "success"
        )
    except Exception as e:
        db.session.rollback()
        flash(
            f"Error al eliminar el archivo: {e}",
            "danger"
        )

    return redirect(url_for("import_excel.historial_importaciones"))


# ==========================================================
# PROCESAR EXCEL
# ==========================================================

@import_excel_bp.route("/excel", methods=["POST"])
@admin_required
def importar_excel():
    try:
        if "archivo" not in request.files:
            flash("No se recibió ningún archivo.", "danger")
            return redirect(url_for("import_excel.pagina_importar"))

        archivo = request.files["archivo"]

        if archivo.filename == "":
            flash("Debe seleccionar un archivo.", "warning")
            return redirect(url_for("import_excel.pagina_importar"))

        nombre = _nombre_seguro_excel(archivo.filename)
        if nombre is None:
            flash("Solo se pueden importar archivos de Excel (.xlsx o .xls).", "danger")
            return redirect(url_for("import_excel.pagina_importar"))

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        ruta = os.path.join(UPLOAD_FOLDER, nombre)
        archivo.save(ruta)

        cantidad = importar_excel_completo(ruta)

        flash(
            f"Importación finalizada. Se cargaron {cantidad} registros.",
            "success"
        )

        return redirect(url_for("dashboard.dashboard"))

    except Exception as e:
        flash(str(e), "danger")
        return redirect(url_for("import_excel.pagina_importar"))