# scripts/asignar_coordenadas_finales.py

from app import create_app
from app.extensions import db
from app.models.store import Store

# Coordenadas exactas por nombre de tienda (clave: nombre en BD)
COORDENADAS = {
    "S 14 C.C. GALERIAS": (4.6479, -74.0736),
    "S 32 C.C. TUNAL VIEJO": (4.5747, -74.1333),
    "S 38 CEDRITOS VIEJO": (4.7600, -74.0350),
    "S-06 VILLA DEL RIO": (4.6000, -74.1560),
    "S-24 CHAPINERO OUTLET": (4.6523, -74.0570),
    "S 10 IBAGUE": (4.4265, -75.2190),
    "S 08 SAN PEDRO PLAZA NEIVA": (2.9519, -75.2886),
    "S 22 VALLEDUPAR GUATAPURI": (10.4631, -73.2532),
    "S 18 BARRANCABERMEJA": (7.0653, -73.8547),
    "S 63 MULTICENTRO CARTAGENA": (10.3933, -75.4817),
    "S 07 BARRANQUILLA PRADO": (10.9683, -74.7813),
    "S 20 CARIBE PLAZA": (10.4144, -75.5297),
    "S 16 BUC/MANGA MEGA MALL": (7.1187, -73.1160),
    "S 51 BUCARAMANGA": (7.1275, -73.1192),
    "S 61 C.C.SAN DIEGO": (6.2444, -75.5650),
    "S 62 C.C. BOCAGRANDE CARTAGENA": (10.4002, -75.5562),
    "S 55 UNICENTRO": (6.2519, -75.5631),
    "S 13 CUCUTA VENTURA PLAZA": (7.8939, -72.5078),
    "TIENDA VIRTUAL": (4.6097, -74.0817),  # Bogotá
    "S 31 FONTIBON": (4.6733, -74.1448),
    "S 30 RESTREPO GATAS": (4.5810, -74.1270),
    "S 12 CEDRITOS MISTER": (4.7602, -74.0351),
    "S 37 P. AMERICAS GRANDE": (4.5969, -74.1500),
    "S 43 RESTREPO OUTLET": (4.5790, -74.1230),
    "S 40 KENNEDY GRANDE": (4.6270, -74.1560),
    "S 52 C.C. BULEVAR 2 PISO": (4.7520, -74.0400),
    "S 57 C.C. SALITRE NUEVO": (4.6474, -74.1003),
    "S 34 DE LA 57": (4.6030, -74.0730),
    "S 47 UNISUR FEMENINO": (4.5793, -74.2158),
    "S 48 C.C. SUBA": (4.7566, -74.0480),
    "S 50 C.C. GRANAHORRAR": (4.6375, -74.1167),
    "S 05 C.C. CENTRO MAYOR": (4.5983, -74.1222),
    "S 26 QUIRIGUA": (4.7074, -74.1036),
    "S 56 C.C. CENTRO CHIA GRANDE": (4.8616, -74.0600),
    "S 23 BULEVAR 1 PISO": (4.7520, -74.0400),
    "S 15 LA 17 CENTRO": (4.6030, -74.0730),
    "S 04 KENNEDY PEQUENO": (4.6270, -74.1560),
    "S 33 QUIRIGUA": (4.7074, -74.1036),  # Misma que Quirigua
}

def main():
    app = create_app()
    with app.app_context():
        tiendas = Store.query.filter(Store.estado == "ACTIVA", Store.nombre != "TOTAL").all()
        for t in tiendas:
            nombre = t.nombre.strip()
            coords = COORDENADAS.get(nombre)
            if coords:
                t.lat, t.lng = coords
                db.session.add(t)
                db.session.commit()
                print(f"{nombre}: asignadas {coords}")
            else:
                print(f"{nombre}: NO tiene coordenadas en el diccionario -> revisar")

        print("Proceso finalizado.")

if __name__ == "__main__":
    main()