
from pathlib import Path
import os
from dotenv import load_dotenv
from cliente_thingsboard import ClienteThingsBoard

load_dotenv(Path(__file__).resolve().parent / ".env")
tb = ClienteThingsBoard(
    url=os.getenv("TB_URL", "https://eu.thingsboard.cloud"),
    usuario=os.environ["TB_USUARIO"],
    contrasena=os.environ["TB_PASSWORD"],
    dispositivo_id=os.environ["TB_DEVICE_ID"],
    token_escritura=os.getenv("TB_TOKEN_PREDICCIONES", ""),
    clave_temperatura=os.getenv("TB_CLAVE_TEMPERATURA", "temperatura_media"),
    clave_humedad=os.getenv("TB_CLAVE_HUMEDAD", "humedad"),
)
try:
    medidas = tb.leer_ultimas_medidas()
    print(f"Temperatura: {medidas.temperatura} °C | Humedad: {medidas.humedad} %")
    print(f"Marcas ThingsBoard (ms): {medidas.ts_temperatura_ms} / {medidas.ts_humedad_ms}")
finally:
    tb.cerrar()
