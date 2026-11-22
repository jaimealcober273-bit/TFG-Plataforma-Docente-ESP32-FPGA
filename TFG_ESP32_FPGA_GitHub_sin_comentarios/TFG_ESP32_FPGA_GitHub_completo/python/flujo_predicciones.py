
import argparse
import csv
import os
from datetime import datetime, timezone
from pathlib import Path
import time

from dotenv import load_dotenv

from cliente_thingsboard import ClienteThingsBoard
from comunicacion_mkr import MKR_UDP, MKR_Serie
from exportar_excel import COLUMNAS, generar_excel

BASE = Path(__file__).resolve().parent

def config(nombre, por_defecto=""):
    return os.environ.get(nombre, por_defecto).strip()

def obligatorio(nombre):
    valor = config(nombre)
    if not valor:
        raise ValueError(f"Falta configurar {nombre} en python/.env")
    return valor

def guardar_registro(ruta, datos):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not ruta.exists() or ruta.stat().st_size == 0
    with ruta.open("a", encoding="utf-8", newline="") as archivo:
        writer = csv.DictWriter(archivo, fieldnames=[nombre for nombre, _ in COLUMNAS])
        if nuevo:
            writer.writeheader()
        writer.writerow(datos)

def configurar():
    load_dotenv(BASE / ".env", override=False)
    tb = ClienteThingsBoard(
        url=config("TB_URL", "https://eu.thingsboard.cloud"),
        usuario=obligatorio("TB_USUARIO"),
        contrasena=obligatorio("TB_PASSWORD"),
        dispositivo_id=obligatorio("TB_DEVICE_ID"),
        token_escritura=obligatorio("TB_TOKEN_PREDICCIONES"),
        clave_temperatura=config("TB_CLAVE_TEMPERATURA", "temperatura_media"),
        clave_humedad=config("TB_CLAVE_HUMEDAD", "humedad"),
        clave_temp_pred=config("TB_CLAVE_TEMP_PRED", "temperatura_predicha"),
        clave_hum_pred=config("TB_CLAVE_HUM_PRED", "humedad_predicha"),
    )
    modo = config("MKR_MODO", "udp").lower()
    if modo == "udp":
        mkr = MKR_UDP(obligatorio("MKR_IP"), config("MKR_PUERTO_UDP", "5005"),
                      config("MKR_TIMEOUT", "5"))
    elif modo == "serial":
        mkr = MKR_Serie(obligatorio("MKR_PUERTO_SERIE"),
                        config("MKR_BAUDIOS", "115200"), config("MKR_TIMEOUT", "5"))
    else:
        raise ValueError("MKR_MODO debe ser udp o serial")
    return tb, mkr

def ejecutar(una_vez=False):
    tb, mkr = configurar()
    csv_path = BASE / config("RESULTADOS_CSV", "resultados/medidas_predicciones.csv")
    excel_path = BASE / config("RESULTADOS_EXCEL", "resultados/medidas_predicciones.xlsx")
    intervalo = max(0.2, float(config("INTERVALO_SEGUNDOS", "5")))
    visto = None
    try:
        while True:
            try:
                medidas = tb.leer_ultimas_medidas()
                if medidas.identificador == visto:
                    print("Sin nuevas medidas en ThingsBoard")
                else:
                    temperatura_pred, humedad_pred = mkr.predecir(medidas.temperatura, medidas.humedad)
                    enviado = True
                    try:
                        tb.publicar_prediccion(temperatura_pred, humedad_pred)
                    except Exception as exc:
                        enviado = False
                        print(f"La predicción se obtuvo, pero no se pudo publicar: {exc}")
                    guardar_registro(csv_path, {
                        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "ts_temperatura_ms": medidas.ts_temperatura_ms,
                        "ts_humedad_ms": medidas.ts_humedad_ms,
                        "temperatura_medida_c": medidas.temperatura,
                        "humedad_medida_pct": medidas.humedad,
                        "temperatura_predicha_c": temperatura_pred,
                        "humedad_predicha_pct": humedad_pred,
                        "publicacion_ok": enviado,
                    })
                    generar_excel(csv_path, excel_path)
                    visto = medidas.identificador
                    print(f"Medidas: {medidas.temperatura:.2f} °C, {medidas.humedad:.2f} % | "
                          f"Predicción MKR: {temperatura_pred:.2f} °C, {humedad_pred:.2f} % | "
                          f"ThingsBoard: {'OK' if enviado else 'ERROR'}")
            except Exception as exc:
                print(f"Error de adquisición o de comunicación: {type(exc).__name__}: {exc}")
                if una_vez:
                    raise
            if una_vez:
                return
            time.sleep(intervalo)
    finally:
        mkr.cerrar()
        tb.cerrar()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Captura medidas, comunica con MKR y publica predicciones")
    parser.add_argument("--una-vez", action="store_true", help="Realiza un solo ciclo")
    args = parser.parse_args()
    ejecutar(una_vez=args.una_vez)
