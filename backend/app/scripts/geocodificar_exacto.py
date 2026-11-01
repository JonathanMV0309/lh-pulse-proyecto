# scripts/geocodificar_exacto.py

import time
import requests
from app import create_app
from app.extensions import db
from app.models.store import Store

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "LHSCORE/1.0 (contacto@ejemplo.test)"}

# Diccionario con direcciones exactas por nombre interno
DIRECCIONES_EXACTAS = {
    "S 14 C.C. GALERIAS": "Calle 53 Nº 25-81 Local 1001/1002, Bogotá",
    "S 32 C.C. TUNAL VIEJO": "Calle 47B Sur Nº 24B-33 Local 1061, Bogotá",
    "S 38 CEDRITOS VIEJO": "Calle 150 Nº 16-56 Locales 1-28/29, Bogotá",
    "S-06 VILLA DEL RIO": "Diagonal 57C Sur Nº 62-60 Local 170, Bogotá",
    "S-24 CHAPINERO OUTLET": "Carrera 13 Nº 57-23, Bogotá",
    "S 10 IBAGUE": "Carrera 3 Nº 12-54 Local 129, Ibagué",
    "S 08 SAN PEDRO PLAZA NEIVA": "Carrera 8 Nº 38-42 Locales 128/129, Neiva",
    "S 22 VALLEDUPAR GUATAPURI": "Diagonal 10 Nº 6-15 Locales 122/123, Valledupar",
    "S 18 BARRANCABERMEJA": "Transversal 55A Nº 57-03 Local 121, Barrancabermeja",
    "S 63 MULTICENTRO CARTAGENA": "C.C. Multicentro La Plazuela Local 1-39/1-65, Cartagena",
    "S 07 BARRANQUILLA PRADO": "Carrera 50 No 48-227 Local 188/189, Barranquilla",
    "S 20 CARIBE PLAZA": "Calle 29D Nº 22-150 Locales 131/132/133, Cartagena",
    "S 16 BUC/MANGA MEGA MALL": "Carrera 33A Nº 29-15 Locales 14/15/16, Bucaramanga",
    "S 51 BUCARAMANGA": "Avenida Samanais Nº 41-40 Local 131/171, Bucaramanga",
    "S 61 C.C.SAN DIEGO": "Calle 34 Nº 43-66 Local 1302, Medellín",
    "S 62 C.C. BOCAGRANDE CARTAGENA": "Avenida San Martin Local 120, Cartagena",
    "S 55 UNICENTRO": "Cra 66B Nº 34A-76 Local 057, Medellín",
    "S 13 CUCUTA VENTURA PLAZA": "Calle 10 Nº E-94 Locales 133/133A, Cúcuta",
    "TIENDA VIRTUAL": "Bogotá, Colombia",
    "S 31 FONTIBON": "Carrera 100 Nº 19-47, Bogotá",
    "S 30 RESTREPO GATAS": "Calle 18 Nº 18-59 Sur, Bogotá",
    "S 12 CEDRITOS MISTER": "Calle 150 Nº 16-56 Local 1-29/30/31, Bogotá",
    "S 37 P. AMERICAS GRANDE": "Transversal 71D Nº 26-94 Sur Local 15-02, Bogotá",
    "S 43 RESTREPO OUTLET": "Carrera 22 Nº 15-15 Sur, Bogotá",
    "S 40 KENNEDY GRANDE": "Carrera 78B Nº 36B-28 Sur, Bogotá",
    "S 52 C.C. BULEVAR 2 PISO": "Avenida Carrera 58 Nº 127-59 Locales 272/273, Bogotá",
    "S 57 C.C. SALITRE NUEVO": "Carrera 68B Nº 40-39 Local 1-19, Bogotá",
    "S 34 DE LA 57": "Carrera 7 Nº 17-91, Bogotá",
    "S 47 UNISUR FEMENINO": "Carrera 3 Nº 29A-02 Local 1023, Soacha",
    "S 48 C.C. SUBA": "Calle 140 Nº 91-19 Locales 7-110/7-113, Bogotá",
    "S 50 C.C. GRANAHORRAR": "Calle 20 Nº 82-52 Local 1-94, Bogotá",
    "S 05 C.C. CENTRO MAYOR": "Calle 38A Sur Nº 34D-50 Local 1033, Bogotá",
    "S 26 QUIRIGUA": "Transversal 94 Nº 82A-56, Bogotá",
    "S 56 C.C. CENTRO CHIA GRANDE": "Avenida Pradilla Nº 900 Este Locales 1042/1043, Chía",
    "S 23 BULEVAR 1 PISO": "Avenida Carrera 58 Nº 127-59 Local 1-89, Bogotá",
    "S 15 LA 17 CENTRO": "Carrera 7 Nº 17-91, Bogotá",
    "S 04 KENNEDY PEQUENO": "Carrera 78B Nº 38C-35 Sur, Bogotá",
    "S 19 C.C. HAYUELOS": "Calle 20 Nº 82-52 Local 1-94, Bogotá",
}

# Coordenadas de respaldo si Nominatim falla (más precisas)
COORDENADAS_RESPALDO = {
    "S 14 C.C. GALERIAS": (4.6478, -74.0736),
    "S 32 C.C. TUNAL VIEJO": (4.5747, -74.1333),
    "S 38 CEDRITOS VIEJO": (4.7600, -74.0350),
    "S-06 VILLA DEL RIO": (4.5999, -74.1558),
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
    "TIENDA VIRTUAL": (4.6097, -74.0817),
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
    "S 19 C.C. HAYUELOS": (4.6375, -74.1167),
}

def geocodificar(query):
    params = {"q": query, "format": "json", "limit": 1}
    try:
        r = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"    Error: {e}")
    return None

def main():
    app = create_app()
    with app.app_context():
        # Limpiar todas las coordenadas para forzar actualización
        db.session.query(Store).update({Store.lat: None, Store.lng: None})
        db.session.commit()
        print("Coordenadas limpiadas.\n")

        tiendas = Store.query.filter(Store.estado == "ACTIVA", Store.nombre != "TOTAL").all()
        total = len(tiendas)
        print(f"Tiendas: {total}\n")

        for i, t in enumerate(tiendas, 1):
            nombre = t.nombre.strip()
            direccion = DIRECCIONES_EXACTAS.get(nombre)
            if direccion:
                query = f"{direccion}, Colombia"
                coords = geocodificar(query)
                if coords:
                    t.lat, t.lng = coords
                    db.session.add(t)
                    db.session.commit()
                    print(f"{i}/{total} {nombre}: geocodificada -> {coords}")
                    time.sleep(1)
                    continue
                else:
                    print(f"{i}/{total} {nombre}: Nominatim falló, usando respaldo")
            else:
                print(f"{i}/{total} {nombre}: sin dirección, usando respaldo")

            # Usar respaldo
            coords = COORDENADAS_RESPALDO.get(nombre)
            if coords:
                t.lat, t.lng = coords
                db.session.add(t)
                db.session.commit()
                print(f"    -> Respaldo: {coords}")
            else:
                print(f"    -> No hay respaldo, se deja sin coordenadas")

        print("\nProceso finalizado.")

if __name__ == "__main__":
    main()