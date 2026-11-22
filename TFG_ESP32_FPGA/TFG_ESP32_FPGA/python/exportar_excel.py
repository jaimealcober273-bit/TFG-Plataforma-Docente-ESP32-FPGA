
import argparse
import csv
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

COLUMNAS = [
    ("fecha_utc", "Fecha UTC"),
    ("ts_temperatura_ms", "Marca temperatura (ms)"),
    ("ts_humedad_ms", "Marca humedad (ms)"),
    ("temperatura_medida_c", "Temperatura medida (°C)"),
    ("humedad_medida_pct", "Humedad medida (%)"),
    ("temperatura_predicha_c", "Temperatura predicha (°C)"),
    ("humedad_predicha_pct", "Humedad predicha (%)"),
    ("publicacion_ok", "Publicada en ThingsBoard"),
]

def generar_excel(csv_path, xlsx_path):
    csv_path, xlsx_path = Path(csv_path), Path(xlsx_path)
    wb = Workbook()
    ws = wb.active
    ws.title = "Medidas y predicciones"
    ws.append([etiqueta for _, etiqueta in COLUMNAS])

    if csv_path.exists():
        with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for fila in reader:
                celdas = []
                for clave, _ in COLUMNAS:
                    valor = fila.get(clave, "")
                    if clave == "fecha_utc" and valor:
                        celdas.append(datetime.fromisoformat(valor.replace("Z", "+00:00")).replace(tzinfo=None))
                    elif clave.startswith("ts_") and valor:
                        celdas.append(int(valor))
                    elif clave in ("temperatura_medida_c", "humedad_medida_pct",
                                   "temperatura_predicha_c", "humedad_predicha_pct") and valor:
                        celdas.append(float(valor))
                    elif clave == "publicacion_ok":
                        celdas.append(valor.lower() in ("true", "1", "si", "sí"))
                    else:
                        celdas.append(valor)
                ws.append(celdas)

    for celda in ws[1]:
        celda.fill = PatternFill("solid", fgColor="17365D")
        celda.font = Font(color="FFFFFF", bold=True)
        celda.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "D2"
    ws.auto_filter.ref = ws.dimensions
    anchos = [22, 25, 25, 23, 22, 24, 22, 27]
    for col, ancho in enumerate(anchos, 1):
        ws.column_dimensions[get_column_letter(col)].width = ancho
    for fila in ws.iter_rows(min_row=2):
        fila[0].number_format = "yyyy-mm-dd hh:mm:ss"
        for celda in fila[3:7]:
            celda.number_format = "0.00"

    notas = wb.create_sheet("Notas")
    notas.append(["Descripción", "Criterio"])
    notas.append(["Medidas", "Últimos valores obtenidos desde ThingsBoard para cada clave"])
    notas.append(["Predicciones", "Valores devueltos por la MKR en esa consulta"])
    notas.append(["Interpretación", "No se supone que la predicción corresponde al mismo instante que la medida"])
    notas.append(["Validación", "Para obtener errores de predicción hace falta alinear la predicción con la medida futura correspondiente"])
    notas.column_dimensions["A"].width = 23
    notas.column_dimensions["B"].width = 100
    for celda in notas[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="17365D")
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(xlsx_path)
    return ws.max_row - 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Genera Excel a partir del CSV de predicciones")
    parser.add_argument("--csv", default="resultados/medidas_predicciones.csv")
    parser.add_argument("--excel", default="resultados/medidas_predicciones.xlsx")
    argumentos = parser.parse_args()
    n = generar_excel(argumentos.csv, argumentos.excel)
    print(f"Excel generado: {argumentos.excel} ({n} registros)")
