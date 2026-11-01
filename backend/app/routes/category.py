from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models.category import Category

category_bp = Blueprint(
    "category",
    __name__,
    url_prefix="/api/categories"
)


# ==========================
# LISTAR
# ==========================
@category_bp.route("/", methods=["GET"])
def get_categories():

    categories = Category.query.all()

    resultado = []

    for c in categories:
        resultado.append({
            "id": c.id,
            "nombre": c.nombre,
            "descripcion": c.descripcion,
            "activa": c.activa
        })

    return jsonify(resultado)


# ==========================
# CREAR
# ==========================
@category_bp.route("/", methods=["POST"])
def create_category():

    data = request.get_json()

    categoria = Category(
        nombre=data["nombre"],
        descripcion=data.get("descripcion")
    )

    db.session.add(categoria)
    db.session.commit()

    return jsonify({
        "mensaje": "Categoría creada correctamente"
    }), 201