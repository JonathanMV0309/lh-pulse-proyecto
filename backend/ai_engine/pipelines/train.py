"""Alias compatible del entrenamiento de ventas v2."""

from ai_engine.pipelines.train_ampliado import entrenar_modelo_ampliado


def main():
    entrenar_modelo_ampliado()


if __name__ == "__main__":
    main()
