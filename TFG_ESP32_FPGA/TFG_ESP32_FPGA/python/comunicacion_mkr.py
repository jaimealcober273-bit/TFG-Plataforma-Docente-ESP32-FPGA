

import json
import math
import socket
import time

def interpretar_prediccion(mensaje):

    if isinstance(mensaje, bytes):
        mensaje = mensaje.decode("utf-8", errors="strict")
    mensaje = mensaje.strip()
    if not mensaje:
        raise ValueError("Respuesta vacía de la MKR")
    if mensaje.startswith("{"):
        datos = json.loads(mensaje)
        temperatura = float(datos.get("temperatura_predicha", datos.get("temperatura")))
        humedad = float(datos.get("humedad_predicha", datos.get("humedad")))
    else:
        if mensaje.upper().startswith("PRED:"):
            mensaje = mensaje.split(":", 1)[1].strip()
        campos = mensaje.split(",")
        if len(campos) != 2:
            raise ValueError("Se esperaban dos predicciones separadas por coma")
        temperatura, humedad = (float(campo.strip()) for campo in campos)
    if not (math.isfinite(temperatura) and math.isfinite(humedad)):
        raise ValueError("La MKR devolvió un valor no finito")
    return temperatura, humedad

def formatear_medidas(temperatura, humedad):
    if not (math.isfinite(temperatura) and math.isfinite(humedad)):
        raise ValueError("Las medidas deben ser numéricas y finitas")
    return f"{temperatura:.2f},{humedad:.2f}\n".encode("ascii")

class MKR_UDP:

    def __init__(self, host, puerto=5005, timeout=5):
        self.host, self.puerto, self.timeout = host, int(puerto), float(timeout)

    def predecir(self, temperatura, humedad):
        paquete = formatear_medidas(temperatura, humedad)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(self.timeout)
            sock.sendto(paquete, (self.host, self.puerto))
            respuesta, origen = sock.recvfrom(2048)

            ip_destino = socket.gethostbyname(self.host)
            if origen[0] != ip_destino:
                raise ValueError("La respuesta UDP no procede de la MKR configurada")
            return interpretar_prediccion(respuesta)

    def cerrar(self):
        pass

class MKR_Serie:

    def __init__(self, puerto, baudios=115200, timeout=5, espera_inicio=2):
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError("Falta pyserial: pip install -r requirements.txt") from exc
        self.timeout = float(timeout)
        self.serial = serial.Serial(puerto, baudrate=int(baudios), timeout=0.5,
                                    write_timeout=self.timeout)
        if espera_inicio:
            time.sleep(float(espera_inicio))
        self.serial.reset_input_buffer()

    def predecir(self, temperatura, humedad):
        self.serial.write(formatear_medidas(temperatura, humedad))
        self.serial.flush()
        fin = time.monotonic() + self.timeout
        while time.monotonic() < fin:
            linea = self.serial.readline()
            if not linea:
                continue
            try:
                return interpretar_prediccion(linea)
            except (ValueError, UnicodeError, TypeError):

                continue
        raise TimeoutError("No llegó ninguna predicción válida desde la MKR")

    def cerrar(self):
        self.serial.close()
