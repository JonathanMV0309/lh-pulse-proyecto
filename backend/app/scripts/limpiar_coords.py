from app import create_app
from app.extensions import db
from app.models.store import Store

app = create_app()
with app.app_context():
    db.session.query(Store).update({Store.lat: None, Store.lng: None})
    db.session.commit()
    print("Coordenadas limpiadas.")