
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv
from cliente_thingsboard import ClienteThingsBoard

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Envía predicciones de prueba a ThingsBoard")
    parser.add_argument("--temperatura", required=True, type=float)
    parser.add_argument("--humedad", required=True, type=float)
    valores = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parent / ".env")
    tb = ClienteThingsBoard(
        url=os.getenv("TB_URL", "https://eu.thingsboard.cloud"),
        usuario="", contrasena="", dispositivo_id="",
        token_escritura=os.environ["TB_TOKEN_PREDICCIONES"],
        clave_temp_pred=os.getenv("TB_CLAVE_TEMP_PRED", "temperatura_predicha"),
        clave_hum_pred=os.getenv("TB_CLAVE_HUM_PRED", "humedad_predicha"),
    )
    try:
        tb.publicar_prediccion(valores.temperatura, valores.humedad)
        print("Predicciones publicadas")
    finally:
        tb.cerrar()
