# scripts/cargar_coordenadas_json.py
import json
from app import create_app
from app.extensions import db
from app.models.store import Store

def main():
    with open('coordenadas_tiendas.json', 'r', encoding='utf-8') as f:
        datos = json.load(f)  # formato: {"nombre_tienda": [lat, lng]}

    app = create_app()
    with app.app_context():
        for nombre, coords in datos.items():
            tienda = Store.query.filter(Store.nombre == nombre).first()
            if tienda:
                tienda.lat, tienda.lng = coords
                db.session.add(tienda)
                db.session.commit()
                print(f"{nombre}: {coords}")
            else:
                print(f"No se encontró {nombre}")

if __name__ == "__main__":
    main()