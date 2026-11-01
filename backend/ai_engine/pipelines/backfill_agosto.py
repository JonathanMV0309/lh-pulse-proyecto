"""El backfill fijo de agosto fue retirado; use AI_DATA_CUTOFF y el pipeline v2."""


def main():
    raise SystemExit(
        "Comando retirado. Configure AI_DATA_CUTOFF=AAAAMM y ejecute "
        "preparar_dataset_ampliado, train_ampliado y predict_ampliado."
    )


if __name__ == "__main__":
    main()
