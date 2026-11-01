import pandas as pd


def analizar_excel(ruta):

    excel = pd.ExcelFile(ruta)

    resultado = {}

    for hoja in excel.sheet_names:

        df = pd.read_excel(
            ruta,
            sheet_name=hoja,
            header=None
        )


        resultado[hoja] = {

            "filas": len(df),

            "columnas": len(df.columns),

            "preview": df.head(8)
            .fillna("")
            .to_dict(orient="records")

        }


    return resultado