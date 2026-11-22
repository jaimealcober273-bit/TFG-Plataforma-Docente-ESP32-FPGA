

from dataclasses import dataclass
from typing import Optional

import requests

@dataclass(frozen=True)
class Medidas:
    temperatura: float
    humedad: float
    ts_temperatura_ms: int
    ts_humedad_ms: int

    @property
    def identificador(self):
        return (self.ts_temperatura_ms, self.ts_humedad_ms)

class ClienteThingsBoard:
    def __init__(self, url, usuario, contrasena, dispositivo_id, token_escritura,
                 clave_temperatura="temperatura_media", clave_humedad="humedad",
                 clave_temp_pred="temperatura_predicha", clave_hum_pred="humedad_predicha",
                 timeout=10):
        self.url = url.rstrip("/")
        self.usuario = usuario
        self.contrasena = contrasena
        self.dispositivo_id = dispositivo_id
        self.token_escritura = token_escritura
        self.clave_temperatura = clave_temperatura
        self.clave_humedad = clave_humedad
        self.clave_temp_pred = clave_temp_pred
        self.clave_hum_pred = clave_hum_pred
        self.timeout = timeout
        self.sesion = requests.Session()
        self._jwt: Optional[str] = None

    def _autenticar(self):
        respuesta = self.sesion.post(
            f"{self.url}/api/auth/login",
            json={"username": self.usuario, "password": self.contrasena},
            timeout=self.timeout,
        )
        respuesta.raise_for_status()
        self._jwt = respuesta.json()["token"]

    def leer_ultimas_medidas(self):

        if not self._jwt:
            self._autenticar()
        endpoint = f"{self.url}/api/plugins/telemetry/DEVICE/{self.dispositivo_id}/values/timeseries"
        params = {"keys": f"{self.clave_temperatura},{self.clave_humedad}"}
        cabeceras = {"X-Authorization": f"Bearer {self._jwt}"}
        respuesta = self.sesion.get(endpoint, params=params, headers=cabeceras, timeout=self.timeout)
        if respuesta.status_code == 401:
            self._autenticar()
            cabeceras["X-Authorization"] = f"Bearer {self._jwt}"
            respuesta = self.sesion.get(endpoint, params=params, headers=cabeceras, timeout=self.timeout)
        respuesta.raise_for_status()
        datos = respuesta.json()
        try:
            t = datos[self.clave_temperatura][0]
            h = datos[self.clave_humedad][0]
            return Medidas(float(t["value"]), float(h["value"]), int(t["ts"]), int(h["ts"]))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError("ThingsBoard no devuelve valores válidos para las claves configuradas") from exc

    def publicar_prediccion(self, temperatura, humedad):

        url = f"{self.url}/api/v1/{self.token_escritura}/telemetry"
        datos = {self.clave_temp_pred: float(temperatura), self.clave_hum_pred: float(humedad)}
        respuesta = self.sesion.post(url, json=datos, timeout=self.timeout)
        respuesta.raise_for_status()

    def cerrar(self):
        self.sesion.close()
