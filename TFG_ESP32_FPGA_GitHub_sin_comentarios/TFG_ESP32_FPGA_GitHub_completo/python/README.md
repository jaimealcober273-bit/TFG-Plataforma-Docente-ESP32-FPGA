# Python: ThingsBoard ↔ MKR Vidor 4000

`flujo_predicciones.py` lee la última temperatura y humedad de ThingsBoard, envía ambas a la MKR, recibe **dos predicciones calculadas por la placa** (no las calcula Python), publica los resultados en ThingsBoard y registra las medidas y predicciones en CSV y Excel.

## Preparación

```bash
cd python
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Copia `.env.example` a `.env` y rellena `TB_USUARIO`, `TB_PASSWORD` y `TB_DEVICE_ID` (para consultar telemetría), además de `TB_TOKEN_PREDICCIONES` (para publicar predicciones). **El token del dispositivo de ThingsBoard no permite por sí solo consultar su histórico**: para leer se requieren credenciales de usuario o un JWT autorizado.

Las medidas se buscan en las claves `temperatura_media` y `humedad`. Se publican resultados con las claves **distintas** `temperatura_predicha` y `humedad_predicha`, para no sobrescribir las medidas. Los cuatro nombres son configurables.

## Protocolo con la MKR

El transporte predeterminado es UDP, `MKR_MODO=udp`, con `MKR_IP` y `MKR_PUERTO_UDP`. También existe `MKR_MODO=serial`, para un firmware que utilice puerto serie.

**El código original de la MKR no se distribuye**, por proceder de un tercero. Por tanto, este repositorio **no demuestra** que la placa implemente el formato siguiente: el programa de la MKR tiene que ser compatible con él o se tendrá que adaptar `comunicacion_mkr.py`.

Formato propuesto (texto ASCII, una muestra por mensaje):

```text
Python -> MKR: 23.00,45.00\n
MKR -> Python: 23.40,44.80\n
```

La respuesta también puede incluir `PRED:` o estar codificada como JSON con claves `temperatura_predicha` y `humedad_predicha`. Para UDP, la respuesta debe enviarse al puerto de origen del paquete. Los valores son números decimales en grados Celsius y porcentaje, respectivamente.

## Ejecutar

```bash
python leer_thingsboard.py                 # Comprueba solo la lectura
python flujo_predicciones.py --una-vez    # Una muestra completa
python flujo_predicciones.py              # Una consulta cada 5 segundos
python enviar_thingsboard.py --temperatura 23.4 --humedad 44.8
python exportar_excel.py                  # Regenera el Excel a partir del CSV
```

Se crean `resultados/medidas_predicciones.csv` y `resultados/medidas_predicciones.xlsx`. Se registran los últimos valores medidos y los predichos, con fecha de consulta y marca temporal de ThingsBoard. **No se calcula MAE/RMSE automáticamente**: no sería correcto comparar una predicción del instante siguiente con la medida del instante actual sin alinear ambas en el tiempo.

## Limitaciones

- Los archivos Python son una implementación reconstruida del flujo descrito; no son una copia recuperada de los ZIP antiguos de validación.
- No hay firmware de MKR ni bitstream de Cyclone 10 LP en este repositorio; no se puede comprobar la compatibilidad extremo a extremo sin ellos.
- No se han efectuado conexiones reales a ThingsBoard ni a la MKR durante la preparación del repositorio.
- El Excel se regenera al incorporar una lectura nueva; para sesiones muy largas conviene exportarlo al terminar desde el CSV.
