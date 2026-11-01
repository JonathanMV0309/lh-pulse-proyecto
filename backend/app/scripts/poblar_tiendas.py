from app import create_app
from app.extensions import db
from app.models import Store


CLASIFICACION_TIENDAS = {

    # ==========================
    # BOGOTÁ - FRÍO
    # ==========================

    "S-04": ("Bogotá", "Frío"),
    "S-05": ("Bogotá", "Frío"),
    "S-06": ("Bogotá", "Frío"),
    "S-12": ("Bogotá", "Frío"),
    "S-14": ("Bogotá", "Frío"),
    "S-15": ("Bogotá", "Frío"),
    "S-19": ("Bogotá", "Frío"),
    "S-23": ("Bogotá", "Frío"),
    "S-24": ("Bogotá", "Frío"),
    "S-26": ("Bogotá", "Frío"),
    "S-30": ("Bogotá", "Frío"),
    "S-31": ("Bogotá", "Frío"),
    "S-32": ("Bogotá", "Frío"),
    "S-34": ("Bogotá", "Frío"),
    "S-37": ("Bogotá", "Frío"),
    "S-38": ("Bogotá", "Frío"),
    "S-40": ("Bogotá", "Frío"),
    "S-43": ("Bogotá", "Frío"),
    "S-47": ("Bogotá", "Frío"),
    "S-48": ("Bogotá", "Frío"),
    "S-50": ("Bogotá", "Frío"),
    "S-52": ("Bogotá", "Frío"),
    "S-57": ("Bogotá", "Frío"),

    # ==========================
    # CHÍA - FRÍO
    # ==========================

    "S-56": ("Chía", "Frío"),

    # ==========================
    # IBAGUÉ - TEMPLADO
    # ==========================

    # ==========================
# IBAGUÉ - TEMPLADO
# ==========================

"S-10": ("Ibagué", "Templado"),

# ==========================
# MEDELLÍN - TEMPLADO
# ==========================

"S-55": ("Medellín", "Templado"),

    "S-08": ("Neiva", "Cálido"),

    # ==========================
    # CÚCUTA - CÁLIDO
    # ==========================

    "S-13": ("Cúcuta", "Cálido"),

    # ==========================
    # VALLEDUPAR - CÁLIDO
    # ==========================

    "S-22": ("Valledupar", "Cálido"),

    # ==========================
    # BARRANCABERMEJA - CÁLIDO
    # ==========================

    "S-18": ("Barrancabermeja", "Cálido"),

    # ==========================
    # BARRANQUILLA - CÁLIDO
    # ==========================

    "S-07": ("Barranquilla", "Cálido"),

    # ==========================
    # CARTAGENA - CÁLIDO
    # ==========================

    "S-20": ("Cartagena", "Cálido"),
    "S-61": ("Cartagena", "Cálido"),
    "S-62": ("Cartagena", "Cálido"),
    "S-63": ("Cartagena", "Cálido"),

    # ==========================
    # BUCARAMANGA - TEMPLADO
    # ==========================

    "S-16": ("Bucaramanga", "Templado"),
    "S-51": ("Bucaramanga", "Templado"),

    "S-03": ("Global", "Global"),
}


def poblar_tiendas():

    app = create_app()

    with app.app_context():

        actualizadas = 0
        no_encontradas = []
        sin_clasificar = []

        tiendas = Store.query.all()

        print("=" * 60)
        print("ACTUALIZANDO CIUDAD Y CLIMA DE TIENDAS")
        print("=" * 60)

        for tienda in tiendas:

            codigo = str(tienda.codigo).strip()

            # No modificar filas especiales
            if codigo in ("TOTA", "TOTAL"):
                sin_clasificar.append(codigo)
                continue

            datos = CLASIFICACION_TIENDAS.get(codigo)

            if not datos:
                no_encontradas.append(codigo)
                continue

            ciudad, clima = datos

            tienda.ciudad = ciudad
            tienda.clima = clima

            actualizadas += 1

            print(
                f"{codigo} | "
                f"{tienda.nombre} | "
                f"{ciudad} | "
                f"{clima}"
            )

        db.session.commit()

        print("=" * 60)
        print(f"TIENDAS ACTUALIZADAS: {actualizadas}")
        print(f"NO CLASIFICADAS: {len(no_encontradas)}")
        print(f"ESPECIALES: {len(sin_clasificar)}")

        if no_encontradas:
            print("\nCÓDIGOS SIN CLASIFICAR:")
            for codigo in no_encontradas:
                print("-", codigo)

        print("=" * 60)


if __name__ == "__main__":
    poblar_tiendas()