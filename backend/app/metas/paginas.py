"""Pantallas de metas. Solo entregan el HTML: los datos los piden las pantallas a la API (/api/v1)."""
from flask import Blueprint, render_template

from app.utils.permissions import admin_required, login_required

metas_paginas_bp = Blueprint("metas_paginas", __name__, url_prefix="/metas-tienda")


@metas_paginas_bp.get("/")
@login_required
@admin_required
def consulta():
    return render_template("metas_tienda/consulta.html")


@metas_paginas_bp.get("/nueva")
@login_required
@admin_required
def nueva():
    return render_template("metas_tienda/formulario.html", meta_id=None)


@metas_paginas_bp.get("/<int:meta_id>/editar")
@login_required
@admin_required
def editar(meta_id):
    return render_template("metas_tienda/formulario.html", meta_id=meta_id)
