# Plataforma docente de monitorización ambiental con ESP32 y FPGA

Código y archivos de proyecto de un TFG que combina dos nodos sensores ESP32, un receptor ESP32 y una FPGA Nexys 4 DDR. Incluye además los scripts Python para la ampliación experimental de predicción con la Arduino MKR Vidor 4000.

## Sistema principal

```text
ESP32 + DHT11 ── ESP-NOW ──┐
                           ├─> ESP32 receptor ── UART 115200 8N1 ──> Nexys 4 DDR
ESP32 + LM35  ── ESP-NOW ──┘                <── UART (resultados BCD) ────┘
                                          │
                                          └── MQTT ──> ThingsBoard
```

Los tres bytes enviados a la FPGA representan temperatura DHT11, temperatura LM35 y humedad en BCD. La FPGA calcula temperatura máxima, mínima y media entera, y devuelve cuatro bytes BCD: **máxima, mínima, media y humedad**. En el `top.v` entregado, cuatro dígitos del display muestran la temperatura media y humedad; el resto de resultados también se calculan y transmiten.

## Ampliación experimental MKR Vidor 4000

```text
ThingsBoard (temperatura y humedad medidas)
    │ API REST
    ▼
Python ── UDP / serie* ──> Arduino MKR Vidor 4000
    ▲                            │
    └──── predicciones* ─────────┘
    │
    ├──> ThingsBoard (claves de predicción)
    └──> CSV y Excel con medidas y predicciones
```

**\*Interfaz pendiente de contrastar con el firmware de la MKR.** Solo se incluyen los scripts Python de integración; **no se publica el código de la MKR**, que procede de otro proyecto. Estos scripts no calculan predicciones por sí mismos: las reciben de la MKR. La documentación detallada está en [`python/README.md`](python/README.md).

## Archivos

```text
arduino/
  emisor_dht11/                  ESP32 emisor DHT11
  emisor_lm35/                   ESP32 emisor LM35
  receptor/                      ESP32 receptor ESP-NOW, UART y MQTT
fpga/
  rtl/top.v                     Módulo original de FPGA
  sim/tb_top.v                  Testbench original
  constraints/esp32_TFG.xdc     XDC original verificado contra archivo de Vivado
  bitstream/top.bit             Bitstream original de la entrega
  reports/                      Informes de implementación originales
vivado/
  project_TFG/project_TFG.xpr   Proyecto original de Vivado
  project_TFG/project_TFG.srcs/ Fuentes originales en su estructura Vivado
  create_project.tcl            Alternativa para generar un proyecto limpio
python/
  flujo_predicciones.py         Orquesta lectura, MKR, publicación y registro
  cliente_thingsboard.py        Cliente REST ThingsBoard
  comunicacion_mkr.py           Transporte UDP/serie y decodificación
  leer_thingsboard.py           Prueba aislada de lectura
  enviar_thingsboard.py         Prueba aislada de publicación
  exportar_excel.py             Exportación CSV → XLSX
  requirements.txt              Dependencias Python
  .env.example                  Configuración de ejemplo sin secretos
```

## Arduino / ESP32

En cada emisor copia `receiver_mac.example.h` como `receiver_mac.h` e introduce la MAC real del ESP32 receptor. En el receptor, copia `credentials.example.h` como `credentials.h` y configura tu red Wi-Fi y el token de ThingsBoard. Ambos archivos reales se excluyen de Git. Se necesitan los cores Arduino para ESP32 y las bibliotecas adecuadas (DHT y PubSubClient, entre otras).

Pines utilizados: DHT11 GPIO 0; LM35 GPIO 34; TX del receptor GPIO 17 hacia FPGA; RX del receptor GPIO 16 desde FPGA. En el archivo XDC, `esp32_tx` está en **E18** y `esp32_rx` en **D18**. Conecta TX con RX, comparte masa y utiliza niveles de **3,3 V**. Verifica el pinout del PMOD antes de conectar.

## Vivado / Nexys 4 DDR

El archivo [`vivado/project_TFG/project_TFG.xpr`](vivado/project_TFG/project_TFG.xpr) permite abrir el proyecto original, con sus fuentes y restricciones originales. Procede del archivo comprimido facilitado posteriormente, y reemplaza al XDC reconstruido de la versión anterior del repositorio. Dispositivo: `xc7a100tcsg324-1` (Nexys 4 DDR).

También se puede crear un proyecto nuevo desde la raíz del repositorio:

```bash
vivado -mode batch -source vivado/create_project.tcl
```

El proyecto original fue generado con una versión de Vivado anterior; puede requerir conversión al abrirlo con versiones actuales. Se conservan el `top.bit` y dos informes originales como resultados de la compilación aportada. No se incluyen las carpetas de caché ni los directorios de simulación y ejecución generados automáticamente.

El banco de pruebas incluido comprueba la recepción UART y los LED para los bytes `AA`, `55`, `FF` y `00`. **No comprueba automáticamente** toda la secuencia de tres medidas ni los cuatro bytes devueltos.

## Notas y limitaciones

- La transformación BCD asume nibbles válidos; la temperatura media se trunca a entero.
- La trama UART no tiene cabecera ni checksum. La pérdida de un byte puede desalinear la interpretación de medidas.
- El programa del LM35 conserva la calibración experimental `temperatura = voltaje * 11` del archivo aportado. No equivale a la sensibilidad nominal de un LM35 sin acondicionamiento.
- En el emisor DHT11 se eliminó una segunda llamada accidental a `esp_now_send()` que declaraba de nuevo la variable `result`.
- Los scripts Python se han reconstruido según la cadena de trabajo descrita. **No se han recuperado los archivos exactos de las entregas Python anteriores** y no se ha probado su compatibilidad con el firmware MKR.
- No se incluyen credenciales ni firmware de terceros. Antes de publicar, revoca cualquier token o contraseña que estuviera embebido en archivos compartidos anteriormente.
- No hay licencia de redistribución especificada para código ajeno. El repositorio no incluye el código de la MKR Vidor 4000.
