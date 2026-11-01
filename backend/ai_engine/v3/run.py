import argparse
import json

from .pipeline import run_forecast


def main():
    parser = argparse.ArgumentParser(description="Genera el pronóstico L&H V3")
    parser.add_argument("--validar", action="store_true", help="Calcula y valida sin guardar")
    parser.add_argument(
        "--evaluar", action="store_true",
        help="Solo lectura: compara los pronósticos ya publicados contra la venta cerrada real",
    )
    args = parser.parse_args()
    if args.evaluar:
        from .db import get_engine
        from .seguimiento import evaluar_pronosticos
        print(json.dumps(evaluar_pronosticos(get_engine()), ensure_ascii=False, indent=2, default=str))
        return
    output = run_forecast(persist=not args.validar)
    summary = {
        "run_id": output["run_id"],
        "tiendas": int(len(output["stores"])),
        "combinaciones_tienda_linea": int(len(output["forecast"])),
        "venta_total_pronosticada": float(output["stores"]["venta_p50"].sum()),
        "diagnostico": output["diagnostics"],
        "guardado": not args.validar,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
