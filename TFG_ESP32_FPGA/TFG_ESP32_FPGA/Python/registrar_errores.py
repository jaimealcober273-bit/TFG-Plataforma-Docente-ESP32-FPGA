#!/usr/bin/env python3
"""Registra errores de prediccion de MKR Vidor 4000 desde ThingsBoard.

Este programa NO se comunica con la MKR: puente.py obtiene y publica las
predicciones. Este segundo proceso consulta su telemetria y compara cada
prediccion con la primera pareja de medidas reales del instante siguiente.

Claves compatibles con puente.py:
  Entrada real: temperatura_media, humedad
  Prediccion:   predictedTemperature, predictedHumidity
  Opcional:     predictionSourceTs (timestamp en ms de la ultima entrada)

Ejecucion continua: python registrar_errores.py
Analizar dia pasado: python registrar_errores.py --dia 2026-11-16
Dependencia:       python -m pip install requests

Se usan las variables de entorno TB_USUARIO, TB_PASSWORD, TB_DEVICE_ID,
TB_URL si estan presentes; si no, se piden usuario, clave e ID por consola.
"""

import argparse
import bisect
import csv
import getpass
import math
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

import requests

TB_URL = "https://eu.thingsboard.cloud"
CLAVE_T_REAL = "temperatura_media"
CLAVE_H_REAL = "humedad"
CLAVE_T_PRED = "predictedTemperature"
CLAVE_H_PRED = "predictedHumidity"
CLAVE_TS_ORIGEN = "predictionSourceTs"  # opcional; mejora el emparejamiento
LIMITE_POR_PETICION = 1000
ZONA_HORARIA = ZoneInfo("Europe/Madrid")

COLUMNAS = [
    "ts_pred_ms", "fecha_prediccion", "ts_origen_ms",
    "ts_real_ms", "fecha_referencia", "segundos_hasta_referencia",
    "segundos_desde_entrada",
    "temperatura_predicha_C", "temperatura_real_C", "error_temperatura_C",
    "error_absoluto_temperatura_C", "humedad_predicha_pct",
    "humedad_real_pct", "error_humedad_pp", "error_absoluto_humedad_pp",
]


def pedir_variable(nombre, pregunta, secreto=False):
    valor = os.getenv(nombre, "").strip()
    while not valor:
        valor = (getpass.getpass if secreto else input)(pregunta).strip()
    return valor


def fecha_legible(ts_ms):
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).astimezone(
        ZONA_HORARIA
    ).isoformat(timespec="milliseconds")


class ThingsBoard:
    def __init__(self, url, usuario, contrasena, device_id):
        self.url = url.rstrip("/")
        self.usuario = usuario
        self.contrasena = contrasena
        self.device_id = device_id
        self.session = requests.Session()
        self.jwt = None

    def autenticar(self):
        r = self.session.post(
            f"{self.url}/api/auth/login",
            json={"username": self.usuario, "password": self.contrasena},
            timeout=20,
        )
        r.raise_for_status()
        self.jwt = r.json()["token"]

    def obtener_serie(self, clave, inicio_ms, fin_ms):
        """Devuelve serie cronologica; pagina para no perder muestras."""
        if not self.jwt:
            self.autenticar()

        url = (f"{self.url}/api/plugins/telemetry/DEVICE/"
               f"{self.device_id}/values/timeseries")
        serie = []
        siguiente_ms = inicio_ms

        while siguiente_ms <= fin_ms:
            params = {
                "keys": clave, "startTs": siguiente_ms, "endTs": fin_ms,
                "agg": "NONE", "orderBy": "ASC", "limit": LIMITE_POR_PETICION,
            }
            headers = {"X-Authorization": f"Bearer {self.jwt}"}
            r = self.session.get(url, params=params, headers=headers, timeout=20)
            if r.status_code == 401:
                self.autenticar()
                headers["X-Authorization"] = f"Bearer {self.jwt}"
                r = self.session.get(url, params=params, headers=headers, timeout=20)
            r.raise_for_status()
            puntos = r.json().get(clave, [])
            if not puntos:
                break
            for punto in puntos:
                try:
                    ts = int(punto["ts"])
                    valor = float(punto["value"])
                    if math.isfinite(valor) and siguiente_ms <= ts <= fin_ms:
                        serie.append((ts, valor))
                except (ValueError, TypeError, KeyError):
                    pass

            ultimo_ts = max(int(x["ts"]) for x in puntos)
            if ultimo_ts < siguiente_ms:
                raise RuntimeError(f"Paginacion sin avance en la clave {clave!r}")
            if len(puntos) < LIMITE_POR_PETICION:
                break
            siguiente_ms = ultimo_ts + 1

        return sorted(set(serie))

    def cerrar(self):
        self.session.close()


def emparejar(temperaturas, humedades):
    """Las dos claves proceden de una misma publicacion y comparten ts."""
    hum_por_ts = dict(humedades)
    return [(ts, t, hum_por_ts[ts]) for ts, t in temperaturas if ts in hum_por_ts]


def registros_comparados(reales, predicciones, marcas_origen, max_segundos):
    """Empareja cada prediccion con la PRIMERA muestra real posterior.

    Si puente.py publica predictionSourceTs, se usa como instante de la ultima
    muestra de entrada. En caso contrario se usa la hora de publicacion de la
    prediccion: esto presupone que se publico antes de llegar la siguiente
    medida real. La asociacion NO es inequívoca sin predictionSourceTs.
    """
    reales_ts = [p[0] for p in reales]
    pred_ts = dict(marcas_origen)
    filas = []

    for ts_pub, t_pred, h_pred in predicciones:
        ts_origen = round(pred_ts[ts_pub]) if ts_pub in pred_ts else None
        ts_base = ts_origen if ts_origen is not None else ts_pub
        siguiente = bisect.bisect_right(reales_ts, ts_base)
        if siguiente >= len(reales):
            continue  # Todavia no hay valor de referencia posterior.
        ts_real, t_real, h_real = reales[siguiente]
        delta_s = (ts_real - ts_base) / 1000
        if delta_s <= 0 or delta_s > max_segundos:
            continue  # No asociar datos separados por demasiado tiempo.

        error_t = t_pred - t_real
        error_h = h_pred - h_real
        filas.append({
            "ts_pred_ms": ts_pub,
            "fecha_prediccion": fecha_legible(ts_pub),
            "ts_origen_ms": ts_origen if ts_origen is not None else "",
            "ts_real_ms": ts_real,
            "fecha_referencia": fecha_legible(ts_real),
            "segundos_hasta_referencia": f"{(ts_real - ts_pub) / 1000:.3f}",
            "segundos_desde_entrada": f"{delta_s:.3f}",
            "temperatura_predicha_C": f"{t_pred:.4f}",
            "temperatura_real_C": f"{t_real:.4f}",
            "error_temperatura_C": f"{error_t:.4f}",
            "error_absoluto_temperatura_C": f"{abs(error_t):.4f}",
            "humedad_predicha_pct": f"{h_pred:.4f}",
            "humedad_real_pct": f"{h_real:.4f}",
            "error_humedad_pp": f"{error_h:.4f}",
            "error_absoluto_humedad_pp": f"{abs(error_h):.4f}",
        })
    return filas


def guardar_sin_duplicados(ruta, filas):
    """Anade filas nuevas sin duplicar predicciones tras reiniciar el script."""
    ruta = Path(ruta)
    existentes = []
    if ruta.exists() and ruta.stat().st_size > 0:
        with ruta.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != COLUMNAS:
                raise ValueError(
                    f"{ruta} ya existe, pero tiene otras columnas. "
                    "Usa --salida con un nombre distinto."
                )
            existentes = list(reader)

    conocidos = {int(f["ts_pred_ms"]) for f in existentes}
    nuevos = []
    for fila in filas:
        ts = int(fila["ts_pred_ms"])
        if ts not in conocidos:
            conocidos.add(ts)
            nuevos.append(fila)

    if nuevos or not ruta.exists():
        with ruta.open("a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNAS)
            if f.tell() == 0:
                writer.writeheader()
            writer.writerows(nuevos)
    return existentes + nuevos, nuevos


def imprimir_estadisticas(filas):
    if not filas:
        print("Sin pares completos prediccion/referencia.")
        return
    e_t = [float(f["error_temperatura_C"]) for f in filas]
    e_h = [float(f["error_humedad_pp"]) for f in filas]
    intervalos = [float(f["segundos_hasta_referencia"]) for f in filas]
    mae_t = mean(abs(e) for e in e_t)
    mae_h = mean(abs(e) for e in e_h)
    rmse_t = math.sqrt(mean(e * e for e in e_t))
    rmse_h = math.sqrt(mean(e * e for e in e_h))
    print(
        f"Registros: {len(filas)} | "
        f"Temp MAE: {mae_t:.2f} °C, RMSE: {rmse_t:.2f} °C, "
        f"sesgo: {mean(e_t):+.2f} °C | "
        f"Humedad MAE: {mae_h:.2f} pp, RMSE: {rmse_h:.2f} pp, "
        f"sesgo: {mean(e_h):+.2f} pp | "
        f"Intervalo prediccion->referencia medio: {mean(intervalos):.2f} s"
    )


def ejecutar_consulta(tb, inicio_ms, fin_ms, salida, max_segundos):
    print(f"Consultando {fecha_legible(inicio_ms)} -> {fecha_legible(fin_ms)}")
    t_real = tb.obtener_serie(CLAVE_T_REAL, inicio_ms, fin_ms)
    h_real = tb.obtener_serie(CLAVE_H_REAL, inicio_ms, fin_ms)
    t_pred = tb.obtener_serie(CLAVE_T_PRED, inicio_ms, fin_ms)
    h_pred = tb.obtener_serie(CLAVE_H_PRED, inicio_ms, fin_ms)
    marcas_origen = tb.obtener_serie(CLAVE_TS_ORIGEN, inicio_ms, fin_ms)

    reales = emparejar(t_real, h_real)
    predicciones = emparejar(t_pred, h_pred)
    filas = registros_comparados(reales, predicciones, marcas_origen, max_segundos)
    todas, nuevas = guardar_sin_duplicados(salida, filas)
    print(f"Parejas reales: {len(reales)} | Predicciones: {len(predicciones)} "
          f"| Nuevas comparaciones: {len(nuevas)} | Archivo: {salida}")
    for f in nuevas[-5:]:
        print(f"  {f['fecha_prediccion']}: "
              f"T {f['temperatura_predicha_C']} vs {f['temperatura_real_C']} °C "
              f"(e={float(f['error_temperatura_C']):+.2f} °C); "
              f"H {f['humedad_predicha_pct']} vs {f['humedad_real_pct']} % "
              f"(e={float(f['error_humedad_pp']):+.2f} pp)")
    imprimir_estadisticas(todas)
    return len(nuevas)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dia", help="Analizar un dia anterior, YYYY-MM-DD (hora de Madrid), y salir")
    parser.add_argument("--salida", default="resultados_validacion.csv",
                        help="Archivo CSV donde guardar los errores")
    parser.add_argument("--ventana-minutos", type=int, default=30,
                        help="Historico a consultar durante la monitorizacion (30)")
    parser.add_argument("--intervalo", type=float, default=10,
                        help="Segundos entre consultas a ThingsBoard (10)")
    parser.add_argument("--max-segundos", type=float, default=90,
                        help="Separacion maxima admitida hasta la medida real (90)")
    args = parser.parse_args()
    if args.max_segundos <= 0 or args.ventana_minutos <= 0 or args.intervalo <= 0:
        parser.error("--intervalo, --max-segundos y --ventana-minutos deben ser positivos")

    usuario = pedir_variable("TB_USUARIO", "Correo ThingsBoard: ")
    contrasena = pedir_variable("TB_PASSWORD", "Contraseña ThingsBoard: ", secreto=True)
    dispositivo = pedir_variable("TB_DEVICE_ID", "ID (UUID) del dispositivo ThingsBoard: ")
    tb = ThingsBoard(os.getenv("TB_URL", TB_URL), usuario, contrasena, dispositivo)

    try:
        tb.autenticar()
        print("Conectado a ThingsBoard. Este programa no utiliza el puerto USB de la MKR.")
        if args.dia:
            try:
                dia = date.fromisoformat(args.dia)
            except ValueError:
                parser.error("--dia debe tener el formato YYYY-MM-DD")
            inicio = datetime(dia.year, dia.month, dia.day, tzinfo=ZONA_HORARIA)
            fin = inicio + timedelta(days=1)
            ejecutar_consulta(tb, int(inicio.timestamp() * 1000),
                              int(fin.timestamp() * 1000) - 1,
                              args.salida, args.max_segundos)
        else:
            print("Monitorizando errores (Ctrl+C para detener)...")
            while True:
                fin_ms = int(time.time() * 1000)
                inicio_ms = fin_ms - args.ventana_minutos * 60_000
                try:
                    ejecutar_consulta(tb, inicio_ms, fin_ms,
                                      args.salida, args.max_segundos)
                except (requests.RequestException, KeyError, ValueError) as exc:
                    print(f"Error de consulta: {exc}. Se reintentara.")
                time.sleep(args.intervalo)
    except KeyboardInterrupt:
        print("\nRegistro detenido.")
    finally:
        tb.cerrar()


if __name__ == "__main__":
    main()
