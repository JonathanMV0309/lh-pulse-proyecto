"""Compatibilidad: el clasificador independiente fue retirado en la versión 2."""


def main():
    print(
        "El clasificador antiguo fue retirado porque no superaba el baseline. "
        "Ejecuta train_ampliado y luego predict_compliance; la probabilidad ahora "
        "se calcula con el error de backtesting y la meta oficial."
    )


if __name__ == "__main__":
    main()
