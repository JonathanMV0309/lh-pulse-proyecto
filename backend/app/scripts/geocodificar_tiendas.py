# scripts/geocodificar_tiendas.py

import time
import requests
from app import create_app
from app.extensions import db
from app.models.store import Store

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {
    "User-Agent": "LHSCORE/1.0 (contacto@ejemplo.test)"
}

# ---------------------------------------------------------
# DICCIONARIO DE DIRECCIONES POR PALABRA CLAVE
# (basado en tu lista oficial de tiendas)
# ---------------------------------------------------------
DIRECCIONES_CLAVE = [
    ("AV. CHILE", "Calle 72 # 10-34 Locales 207-208, Bogotá"),
    ("BULEVAR 1", "Avenida Carrera 58 Nº 127-59 Local 1-89, Bogotá"),
    ("BULEVAR 2", "Avenida Carrera 58 Nº 127-59 Locales 272/273, Bogotá"),
    ("CEDRITOS VIEJO", "Calle 150 Nº 16-56 Locales 1-28/29, Bogotá"),
    ("CEDRITOS MISTER", "Calle 150 Nº 16-56 Local 1-29/30/31, Bogotá"),
    ("CENTRO MAYOR", "Calle 38A Sur Nº 34D-50 Local 1033, Bogotá"),
    ("CENTRO SUBA", "Calle 140 Nº 91-19 Locales 7-110/7-113, Bogotá"),
    ("GALERIAS", "Calle 53 Nº 25-81 Local 1001/1002, Bogotá"),
    ("HAYUELOS", "Calle 20 Nº 82-52 Local 1-94, Bogotá"),
    ("VILLA DEL RIO", "Diagonal 57C Sur Nº 62-60 Local 170, Bogotá"),
    ("PLAZA DE LAS AMERICAS", "Transversal 71D Nº 26-94 Sur Local 15-02, Bogotá"),
    ("SALITRE", "Carrera 68B Nº 40-39 Local 1-19, Bogotá"),
    ("TUNAL", "Calle 47B Sur Nº 24B-33 Local 1061, Bogotá"),
    ("CENTRO CALLE 17", "Carrera 7 Nº 17-91, Bogotá"),
    ("LA 17", "Carrera 7 Nº 17-91, Bogotá"),
    ("CHAPINERO", "Carrera 13 Nº 57-23, Bogotá"),
    ("FONTIBON", "Carrera 100 Nº 19-47, Bogotá"),
    ("KENNEDY GRANDE", "Carrera 78B Nº 36B-28 Sur, Bogotá"),
    ("KENNEDY PEQUENO", "Carrera 78B Nº 38C-35 Sur, Bogotá"),
    ("KENNEDY OUTLET", "Carrera 78B Nº 38C-35 Sur, Bogotá"),
    ("QUIRIGUA", "Transversal 94 Nº 82A-56, Bogotá"),
    ("RESTREPO GATAS", "Calle 18 Nº 18-59 Sur, Bogotá"),
    ("RESTREPO OUTLET", "Carrera 22 Nº 15-15 Sur, Bogotá"),
    ("SAN DIEGO", "Calle 34 Nº 43-66 Local 1302, Medellín"),
    ("UNICENTRO", "Cra 66B Nº 34A-76 Local 057, Medellín"),
    ("BOCAGRANDE", "Avenida San Martin Local 120, Cartagena"),
    ("CARIBE PLAZA", "Calle 29D Nº 22-150 Locales 131/132/133, Cartagena"),
    ("MULTICENTRO", "C.C. Multicentro La Plazuela Local 1-39/1-65, Cartagena"),
    ("BARRANCABERMEJA", "Transversal 55A Nº 57-03 Local 121, Barrancabermeja"),
    ("PRADO", "Carrera 50 No 48-227 Local 188/189, Barranquilla"),
    ("BUCARAMANGA", "Avenida Samanais Nº 41-40 Local 131/171, Bucaramanga"),
    ("MEGA MALL", "Carrera 33A Nº 29-15 Locales 14/15/16, Bucaramanga"),
    ("CENTRO CHIA", "Avenida Pradilla Nº 900 Este Locales 1042/1043, Chía"),
    ("VENTURA PLAZA", "Calle 10 Nº E-94 Locales 133/133A, Cúcuta"),
    ("COMBEIMA", "Carrera 3 Nº 12-54 Local 129, Ibagué"),
    ("SAN PEDRO PLAZA", "Carrera 8 Nº 38-42 Locales 128/129, Neiva"),
    ("UNISUR", "Carrera 3 Nº 29A-02 Local 1023, Soacha"),
    ("GUATAPURI", "Diagonal 10 Nº 6-15 Locales 122/123, Valledupar"),
    ("TIENDA VIRTUAL", "Bogotá, Colombia"),
    ("GRANAHORRAR", "Calle 20 Nº 82-52 Local 1-94, Bogotá"),
    ("SUBA", "Calle 140 Nº 91-19 Locales 7-110/7-113, Bogotá"),
    ("CENTRO CHIA GRANDE", "Avenida Pradilla Nº 900 Este Locales 1042/1043, Chía"),
    ("CENTRO CHIA", "Avenida Pradilla Nº 900 Este Locales 1042/1043, Chía"),
    ("DE LA 57", "Carrera 7 Nº 17-91, Bogotá"),
]

# Coordenadas de respaldo (lat, lng) para centros comerciales conocidos
COORDENADAS_RESPALDO = {
    "C.C. SALITRE": (4.6474, -74.1003),
    "C.C. GRANAHORRAR": (4.6375, -74.1167),
    "C.C. CENTRO MAYOR": (4.5983, -74.1222),
    "C.C. TUNAL": (4.5714, -74.1333),
    "C.C. PLAZA DE LAS AMERICAS": (4.5969, -74.1500),
    "C.C. BULEVAR": (4.7520, -74.0400),
    "C.C. SAN DIEGO": (6.2444, -75.5650),
    "C.C. UNICENTRO": (6.2519, -75.5631),
    "C.C. CARIBE PLAZA": (10.4144, -75.5297),
    "C.C. BOCAGRANDE": (10.4002, -75.5562),
    "C.C. MULTICENTRO": (10.3933, -75.4817),
    "C.C. PORTAL DEL PRADO": (10.9683, -74.7813),
    "C.C. ACROPOLIS": (7.1275, -73.1192),
    "C.C. MEGA MALL": (7.1187, -73.1160),
    "C.C. CENTRO CHIA": (4.8616, -74.0600),
    "C.C. VENTURA PLAZA": (7.8939, -72.5078),
    "C.C. COMBEIMA": (4.4265, -75.2190),
    "C.C. SAN PEDRO PLAZA": (2.9519, -75.2886),
    "C.C. UNISUR": (4.5793, -74.2158),
    "C.C. GUATAPURI": (10.4631, -73.2532),
}

def buscar_direccion(nombre):
    """Busca una dirección basada en palabras clave dentro del nombre."""
    nombre_upper = nombre.upper()
    for clave, direccion in DIRECCIONES_CLAVE:
        if clave in nombre_upper:
            return direccion
    return None

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

def obtener_coordenadas_respaldo(nombre):
    """Intenta obtener coordenadas de respaldo según nombre."""
    nombre_upper = nombre.upper()
    for clave, coords in COORDENADAS_RESPALDO.items():
        if clave in nombre_upper:
            return coords
    return None

def main():
    app = create_app()
    with app.app_context():
        tiendas = Store.query.filter(Store.estado == "ACTIVA", Store.nombre != "TOTAL").all()
        total = len(tiendas)
        print(f"Tiendas: {total}")

        for i, t in enumerate(tiendas, 1):
            if t.lat is not None and t.lng is not None:
                print(f"{i}/{total} {t.nombre} ya tiene coordenadas, omitiendo.")
                continue

            nombre = t.nombre.strip()
            ciudad = t.ciudad or ""
            direccion = buscar_direccion(nombre)
            if direccion:
                query = f"{direccion}, Colombia"
            else:
                query = f"{nombre}, {ciudad}, Colombia"

            print(f"{i}/{total} Geocodificando '{nombre}' -> {query}")
            coords = geocodificar(query)

            # Si Nominatim no devuelve, intentar respaldo
            if not coords:
                coords = obtener_coordenadas_respaldo(nombre)
                if coords:
                    print(f"    -> Usando coordenadas de respaldo: {coords[0]:.5f}, {coords[1]:.5f}")

            if coords:
                t.lat, t.lng = coords
                db.session.add(t)
                db.session.commit()
                print(f"    -> Asignadas: {coords[0]:.5f}, {coords[1]:.5f}")
            else:
                print("    -> No se encontraron coordenadas (ni respaldo)")

            time.sleep(1)  # Respetar 1 petición/segundo

        print("Proceso finalizado.")

if __name__ == "__main__":
    main()