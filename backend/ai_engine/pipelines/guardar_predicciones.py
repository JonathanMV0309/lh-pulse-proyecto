"""Alias compatible de publicación de predicciones v2."""

from ai_engine.pipelines.guardar_predicciones_ampliadas import guardar_predicciones_ampliadas


def guardar_predicciones():
    return guardar_predicciones_ampliadas()


if __name__ == "__main__":
    guardar_predicciones()
