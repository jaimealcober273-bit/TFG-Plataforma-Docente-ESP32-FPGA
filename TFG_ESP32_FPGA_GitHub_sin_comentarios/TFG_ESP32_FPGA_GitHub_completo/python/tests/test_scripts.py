
import csv
import io
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comunicacion_mkr import interpretar_prediccion, formatear_medidas
from exportar_excel import generar_excel, COLUMNAS
from openpyxl import load_workbook

class TestsMKR(unittest.TestCase):
    def test_csv(self):
        self.assertEqual(interpretar_prediccion(b"PRED:23.50,44.25\n"), (23.5, 44.25))
        self.assertEqual(interpretar_prediccion("23.50,44.25"), (23.5, 44.25))

    def test_json(self):
        self.assertEqual(interpretar_prediccion('{"temperatura_predicha":23,"humedad_predicha":45}'), (23.0, 45.0))

    def test_malformed(self):
        with self.assertRaises(ValueError):
            interpretar_prediccion("Valor no válido")
        with self.assertRaises(ValueError):
            interpretar_prediccion("nan,40")

    def test_request(self):
        self.assertEqual(formatear_medidas(23, 45), b"23.00,45.00\n")

class TestExcel(unittest.TestCase):
    def test_exportacion(self):
        with tempfile.TemporaryDirectory() as d:
            origen = Path(d) / "registro.csv"
            destino = Path(d) / "registro.xlsx"
            with origen.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[clave for clave, _ in COLUMNAS])
                writer.writeheader()
                writer.writerow({"fecha_utc":"2026-11-22T12:00:00+00:00",
                                 "ts_temperatura_ms":"1795348800000", "ts_humedad_ms":"1795348800000",
                                 "temperatura_medida_c":"25", "humedad_medida_pct":"40",
                                 "temperatura_predicha_c":"25.5", "humedad_predicha_pct":"41",
                                 "publicacion_ok":"True"})
            self.assertEqual(generar_excel(origen, destino), 1)
            wb = load_workbook(destino, data_only=True)
            ws = wb["Medidas y predicciones"]
            self.assertEqual(ws.cell(2,4).value, 25)
            self.assertEqual(ws.cell(2,6).value, 25.5)
            self.assertEqual(ws.cell(2,8).value, True)
            self.assertIn("Notas", wb.sheetnames)

if __name__ == "__main__":
    unittest.main()

class TestFlujoAislado(unittest.TestCase):
    def test_cadena_sin_red_ni_mkr_real(self):

        from unittest.mock import patch
        import flujo_predicciones as flujo
        from cliente_thingsboard import Medidas
        class TB:
            def __init__(self):self.publicado = None
            def leer_ultimas_medidas(self): return Medidas(25.0, 40.0, 123, 123)
            def publicar_prediccion(self,t,h): self.publicado=(t,h)
            def cerrar(self): pass
        class MKR:
            def predecir(self,t,h):
                assert (t,h)==(25.0,40.0)
                return (25.5,41.0)
            def cerrar(self): pass
        with tempfile.TemporaryDirectory() as directory:
            tb, mkr = TB(), MKR()
            with patch.object(flujo, "configurar", return_value=(tb,mkr)), \
                 patch.object(flujo, "BASE", Path(directory)):
                flujo.ejecutar(una_vez=True)
            self.assertEqual(tb.publicado, (25.5,41.0))
            self.assertTrue((Path(directory)/"resultados/medidas_predicciones.csv").exists())
            wb=load_workbook(Path(directory)/"resultados/medidas_predicciones.xlsx")
            self.assertEqual(wb.worksheets[0].cell(2,6).value,25.5)
