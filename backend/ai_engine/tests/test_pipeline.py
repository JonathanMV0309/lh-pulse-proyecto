"""Pruebas de calidad del pipeline de IA."""

import unittest

import numpy as np
import pandas as pd

from ai_engine.pipelines.forecast_utils import (
    agregar_rezagos_calendario,
    agregar_variables_temporales,
    metricas_regresion,
    validar_claves_unicas,
)
from ai_engine.pipelines.importar_historico_lineas import RUTA_EXCEL, procesar_inf4
from ai_engine.pipelines.preparar_dataset_ampliado import consolidar_panel


class ForecastPipelineTests(unittest.TestCase):
    def test_importador_inf4_lee_ventas_y_no_porcentajes(self):
        result = procesar_inf4(RUTA_EXCEL)
        totals = result.groupby("anio")["venta_pesos"].sum()
        self.assertGreater(totals[2024], 40_000_000_000)
        self.assertGreater(totals[2025], 40_000_000_000)
        self.assertEqual(result["mes"].nunique(), 12)

    def test_bd_tiene_prioridad_en_solapamientos(self):
        historical = pd.DataFrame([
            {"store_id": 1, "line_id": 1, "anio": 2025, "mes": 1, "venta": 10, "fuente_prioridad": 0}
        ])
        current = pd.DataFrame([
            {"store_id": 1, "line_id": 1, "anio": 2025, "mes": 1, "venta": 20}
        ])
        result = consolidar_panel(historical, current, 202501)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["venta"], 20)

    def test_lag_respeta_mes_calendario_y_no_fila_anterior(self):
        panel = pd.DataFrame([
            {"store_id": 1, "line_id": 1, "anio": 2025, "mes": 1, "venta": 10},
            {"store_id": 1, "line_id": 1, "anio": 2025, "mes": 3, "venta": 30},
        ])
        result = agregar_rezagos_calendario(panel)
        march = result[result["mes"] == 3].iloc[0]
        self.assertTrue(np.isnan(march["venta_lag_1"]))
        self.assertEqual(march["venta_lag_2"], 10)

    def test_rechaza_claves_duplicadas(self):
        duplicated = pd.DataFrame([
            {"store_id": 1, "line_id": 1, "anio": 2025, "mes": 1, "venta": 10},
            {"store_id": 1, "line_id": 1, "anio": 2025, "mes": 1, "venta": 20},
        ])
        with self.assertRaises(ValueError):
            validar_claves_unicas(duplicated)

    def test_mes_usa_codificacion_ciclica(self):
        result = agregar_variables_temporales(pd.DataFrame({"anio": [2025, 2025], "mes": [1, 12]}))
        self.assertNotEqual(result.iloc[0]["mes_sin"], 1)
        self.assertAlmostEqual(result.iloc[1]["mes_sin"], 0.0, places=7)

    def test_metricas_detectan_modelo_perfecto(self):
        metrics = metricas_regresion([10, 20], [10, 20])
        self.assertEqual(metrics["wape"], 0)
        self.assertEqual(metrics["r2"], 1)
        self.assertEqual(metrics["predicciones_negativas"], 0)


if __name__ == "__main__":
    unittest.main()
