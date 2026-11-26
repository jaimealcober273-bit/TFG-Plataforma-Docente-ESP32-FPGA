#!/usr/bin/env python3
"""ThingsBoard -> MKR Vidor 4000 -> ThingsBoard (un solo archivo).

La MKR debe ejecutar un firmware compatible con el protocolo serie descrito
para el TFG: a 9600 baudios, anuncia READY, recibe líneas «T,H», devuelve
ACK mientras acumula las cuatro primeras parejas y responde «PRED T,H» al
realizar una predicción. El cálculo lo hace la FPGA, no este programa.

Instalar:  python -m pip install requests pyserial
Ejecutar: python puente.py

Las credenciales se piden al iniciar o pueden pasarse mediante variables de
entorno TB_USUARIO, TB_PASSWORD, TB_DEVICE_ID, TB_DEVICE_TOKEN, MKR_PUERTO.
No añadas credenciales a un repositorio público.
"""

import getpass
import os
import re
import time
from datetime import datetime, timezone

import requests
import serial

# Configuración: ajusta estas constantes si lo necesitas.
TB_URL = "https://eu.thingsboard.cloud"
CLAVE_TEMPERATURA = "temperatura_media"
CLAVE_HUMEDAD = "humedad"
CLAVE_PRED_TEMPERATURA = "predictedTemperature"
CLAVE_PRED_HUMEDAD = "predictedHumidity"
BAUDIOS_MKR = 9600
INTERVALO_CONSULTA = 5             # segundos
HORAS_HISTORICO = 24               # para recuperar hasta cuatro lecturas iniciales
TOLERANCIA_PAREJA_MS = 0           # las dos claves llegan en la misma publicación

# Reconoce, por ejemplo, «PRED: 22.50,48.00» o «PRED 22.50 48.00».
PATRON_NUMERO = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


def pedir(nombre, etiqueta, secreto=False):
    valor = os.environ.get(nombre, "").strip()
    while not valor:
        valor = (getpass.getpass if secreto else input)(etiqueta).strip()
    return valor


class ThingsBoard:
    def __init__(self, url, usuario, contrasena, dispositivo_id, token):
        self.url = url.rstrip("/")
        self.dispositivo_id = dispositivo_id
        self.token = token
        self.usuario = usuario
        self.contrasena = contrasena
        self.http = requests.Session()
        self.jwt = None

    def autenticar(self):
        r = self.http.post(
            f"{self.url}/api/auth/login",
            json={"username": self.usuario, "password": self.contrasena}, timeout=15
        )
        r.raise_for_status()
        self.jwt = r.json()["token"]

    def obtener_parejas(self):
        """Consulta el histórico real, empareja T/H y devuelve [(ts, T, H), ...]."""
        if not self.jwt:
            self.autenticar()
        ahora_ms = int(time.time() * 1000)
        parametros = {
            "keys": f"{CLAVE_TEMPERATURA},{CLAVE_HUMEDAD}",
            "startTs": ahora_ms - HORAS_HISTORICO * 3_600_000,
            "endTs": ahora_ms,
            "limit": 500,
            "agg": "NONE",
        }
        url = f"{self.url}/api/plugins/telemetry/DEVICE/{self.dispositivo_id}/values/timeseries"
        cabeceras = {"X-Authorization": f"Bearer {self.jwt}"}
        r = self.http.get(url, params=parametros, headers=cabeceras, timeout=15)
        if r.status_code == 401:
            self.autenticar()
            cabeceras["X-Authorization"] = f"Bearer {self.jwt}"
            r = self.http.get(url, params=parametros, headers=cabeceras, timeout=15)
        r.raise_for_status()
        datos = r.json()
        temperaturas = sorted(
            (int(item["ts"]), float(item["value"]))
            for item in datos.get(CLAVE_TEMPERATURA, [])
        )
        humedades = sorted(
            (int(item["ts"]), float(item["value"]))
            for item in datos.get(CLAVE_HUMEDAD, [])
        )

        # Una medida solo se envía si tiene su correspondiente pareja temporal.
        parejas = []
        i = j = 0
        while i < len(temperaturas) and j < len(humedades):
            ts_t, t = temperaturas[i]
            ts_h, h = humedades[j]
            if abs(ts_t - ts_h) <= TOLERANCIA_PAREJA_MS:
                parejas.append((max(ts_t, ts_h), t, h))
                i += 1
                j += 1
            elif ts_t < ts_h:
                i += 1
            else:
                j += 1
        return parejas

    def publicar_prediccion(self, temperatura, humedad):
        r = self.http.post(
            f"{self.url}/api/v1/{self.token}/telemetry",
            json={
                CLAVE_PRED_TEMPERATURA: temperatura,
                CLAVE_PRED_HUMEDAD: humedad,
            },
            timeout=15,
        )
        r.raise_for_status()

    def cerrar(self):
        self.http.close()


def esperar_ready(puerto, timeout=15):
    """Tras conectar por USB, espera el anuncio READY del firmware MKR."""
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        linea = puerto.readline().decode("utf-8", errors="replace").strip()
        if linea:
            print(f"MKR: {linea}")
            if "READY" in linea.upper():
                return
    raise TimeoutError("No se recibió READY de la MKR. Revisa puerto, baudios y firmware.")


def enviar_a_mkr(puerto, temperatura, humedad, timeout=15):
    """Devuelve None si la MKR responde ACK o (T_pred, H_pred) si responde PRED."""
    mensaje = f"{temperatura:.2f},{humedad:.2f}\n"
    puerto.write(mensaje.encode("ascii"))
    puerto.flush()
    fin = time.monotonic() + timeout
    pred_pendiente = False
    while time.monotonic() < fin:
        linea = puerto.readline().decode("utf-8", errors="replace").strip()
        if not linea:
            continue
        print(f"MKR: {linea}")
        mayusculas = linea.upper()
        if mayusculas.startswith("ACK"):
            return None
        if mayusculas.startswith("PRED"):
            pred_pendiente = True
            resto = linea[4:].lstrip(" :;,\t")
        elif pred_pendiente:
            resto = linea
        else:
            continue  # Otros mensajes de depuración de la MKR.
        numeros = PATRON_NUMERO.findall(resto)
        if len(numeros) >= 2:
            return float(numeros[0]), float(numeros[1])
    raise TimeoutError("La MKR no respondió ACK/PRED en el tiempo establecido.")


def main():
    print("Puente ThingsBoard <-> Arduino MKR Vidor 4000")
    usuario = pedir("TB_USUARIO", "Usuario (correo) ThingsBoard: ")
    contrasena = pedir("TB_PASSWORD", "Contraseña ThingsBoard: ", secreto=True)
    dispositivo = pedir("TB_DEVICE_ID", "ID (UUID) del dispositivo ThingsBoard: ")
    token = pedir("TB_DEVICE_TOKEN", "Token de acceso del dispositivo: ", secreto=True)
    puerto_nombre = pedir("MKR_PUERTO", "Puerto de la MKR (por ejemplo COM5 o /dev/ttyACM0): ")

    tb = ThingsBoard(TB_URL, usuario, contrasena, dispositivo, token)
    try:
        tb.autenticar()
        print("Conectado a ThingsBoard.")
        with serial.Serial(puerto_nombre, BAUDIOS_MKR, timeout=0.5, write_timeout=5) as mkr:
            esperar_ready(mkr)
            print("MKR preparada. Consultando telemetría...")
            ultimo_ts = None
            while True:
                try:
                    parejas = tb.obtener_parejas()
                    if ultimo_ts is None:
                        # Arranque: usa las últimas cuatro parejas cronológicas.
                        nuevas = parejas[-4:]
                    else:
                        nuevas = [p for p in parejas if p[0] > ultimo_ts]
                    for ts, t, h in nuevas:
                        fecha = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
                        print(f"[{fecha}] Envío a MKR: {t:.2f} °C, {h:.2f} %")
                        prediccion = enviar_a_mkr(mkr, t, h)
                        ultimo_ts = ts
                        if prediccion is not None:
                            t_pred, h_pred = prediccion
                            tb.publicar_prediccion(t_pred, h_pred)
                            print(f"Predicción publicada: {t_pred:.2f} °C, {h_pred:.2f} %")
                    if not nuevas:
                        print("Sin muestras nuevas.")
                except requests.RequestException as exc:
                    print(f"Error de ThingsBoard: {exc}. Se reintentará la consulta.")
                time.sleep(INTERVALO_CONSULTA)
    except KeyboardInterrupt:
        print("\nPuente detenido.")
    finally:
        tb.cerrar()


if __name__ == "__main__":
    main()
