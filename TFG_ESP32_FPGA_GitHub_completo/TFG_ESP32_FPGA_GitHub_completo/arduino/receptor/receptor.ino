#include <WiFi.h>
#include <esp_now.h>
#include <esp_mac.h>
#include <PubSubClient.h>

// =====================================================
// WiFi + ThingsBoard
// =====================================================
// ====== WiFi + ThingsBoard (EU Cloud) ======
#include "credentials.h"  // Archivo local no incluido en el repositorio
#define TB_SERVER      "eu.thingsboard.cloud"
#define TB_PORT        1883

WiFiClient espClient;
PubSubClient mqtt(espClient);

// =====================================================
// UART hacia la FPGA
// =====================================================
#define RXD 16   // RX del ESP32: recibe desde la FPGA
#define TXD 17   // TX del ESP32: envia hacia la FPGA

// =====================================================
// Estructura recibida por ESP-NOW
// =====================================================
typedef struct struct_message {
  uint8_t id;           // 1 = emisora 1, 2 = emisora 2
  uint8_t temperatura;
  uint8_t humedad;
} struct_message;

struct_message paquetePendiente;

// =====================================================
// Datos de las emisoras
// =====================================================
uint8_t temp1 = 0;
uint8_t temp2 = 0;
uint8_t humedad1 = 0;

bool temp1Recibida = false;
bool temp2Recibida = false;
bool humedadRecibida = false;

volatile bool hayPaqueteNuevo = false;

// =====================================================
// Conversiones BCD
// =====================================================
uint8_t decimalToBCD(uint8_t valor) {
  if (valor > 99) {
    valor = 99;
  }

  uint8_t decenas = valor / 10;
  uint8_t unidades = valor % 10;

  return (decenas << 4) | unidades;
}

uint8_t bcdToDecimal(uint8_t bcd) {
  uint8_t decenas = (bcd >> 4) & 0x0F;
  uint8_t unidades = bcd & 0x0F;

  return decenas * 10 + unidades;
}

// =====================================================
// Conexion WiFi
// =====================================================
void conectarWiFi() {
  WiFi.mode(WIFI_STA);

  Serial.print("Conectando a WiFi: ");
  Serial.println(WIFI_AP);

  WiFi.begin(WIFI_AP, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WiFi conectado");

  Serial.print("IP ESP32 receptora: ");
  Serial.println(WiFi.localIP());
}

// =====================================================
// Conexion a ThingsBoard
// =====================================================
void conectarThingsBoard() {
  mqtt.setServer(TB_SERVER, TB_PORT);

  while (!mqtt.connected()) {
    Serial.print("Conectando a ThingsBoard... ");

    if (mqtt.connect("ESP32_Receptora", TOKEN, NULL)) {
      Serial.println("conectado");
    } else {
      Serial.print("error, rc=");
      Serial.print(mqtt.state());
      Serial.println(" reintentando en 3 segundos");
      delay(3000);
    }
  }
}

// =====================================================
// Enviar telemetria a ThingsBoard
// =====================================================
void enviarAThingsBoard(uint8_t tempMaxima,
                        uint8_t tempMinima,
                        uint8_t tempMedia,
                        uint8_t humedad) {
  if (!mqtt.connected()) {
    conectarThingsBoard();
  }

  mqtt.loop();

  char payload[160];

  snprintf(payload, sizeof(payload),
           "{\"temperatura_maxima\":%u,"
           "\"temperatura_minima\":%u,"
           "\"temperatura_media\":%u,"
           "\"humedad\":%u}",
           tempMaxima,
           tempMinima,
           tempMedia,
           humedad);

  Serial.println("----- Enviando a ThingsBoard -----");
  Serial.println(payload);

  bool enviado = mqtt.publish("v1/devices/me/telemetry", payload);

  if (enviado) {
    Serial.println("Datos enviados correctamente a ThingsBoard");
  } else {
    Serial.println("Error enviando datos a ThingsBoard");
  }

  Serial.println("----------------------------------");
}

// =====================================================
// Limpiar buffer UART de FPGA
// =====================================================
void limpiarBufferFpga() {
  while (Serial1.available() > 0) {
    Serial1.read();
  }
}

// =====================================================
// Recibir respuesta desde FPGA
//
// La FPGA devuelve:
//
// byte 1 = temperatura maxima en BCD
// byte 2 = temperatura minima en BCD
// byte 3 = temperatura media en BCD
// byte 4 = humedad en BCD
// =====================================================
bool recibirDesdeFpga(uint8_t &tempMaximaFpga,
                      uint8_t &tempMinimaFpga,
                      uint8_t &tempMediaFpga,
                      uint8_t &humedadFpga) {

  unsigned long tiempoInicio = millis();
  const unsigned long timeout = 1000;

  while (Serial1.available() < 4 &&
         millis() - tiempoInicio < timeout) {
    delay(1);
  }

  if (Serial1.available() >= 4) {

    uint8_t tempMaxBCD   = Serial1.read();
    uint8_t tempMinBCD   = Serial1.read();
    uint8_t tempMediaBCD = Serial1.read();
    uint8_t humedadBCD   = Serial1.read();

    tempMaximaFpga = bcdToDecimal(tempMaxBCD);
    tempMinimaFpga = bcdToDecimal(tempMinBCD);
    tempMediaFpga  = bcdToDecimal(tempMediaBCD);
    humedadFpga    = bcdToDecimal(humedadBCD);

    Serial.println("----- Respuesta recibida desde FPGA -----");

    Serial.print("Temperatura maxima recibida desde FPGA en BCD: 0x");
    if (tempMaxBCD < 0x10) Serial.print("0");
    Serial.println(tempMaxBCD, HEX);

    Serial.print("Temperatura minima recibida desde FPGA en BCD: 0x");
    if (tempMinBCD < 0x10) Serial.print("0");
    Serial.println(tempMinBCD, HEX);

    Serial.print("Temperatura media recibida desde FPGA en BCD: 0x");
    if (tempMediaBCD < 0x10) Serial.print("0");
    Serial.println(tempMediaBCD, HEX);

    Serial.print("Humedad recibida desde FPGA en BCD: 0x");
    if (humedadBCD < 0x10) Serial.print("0");
    Serial.println(humedadBCD, HEX);

    Serial.println();

    Serial.print("Temperatura maxima desde FPGA: ");
    Serial.println(tempMaximaFpga);

    Serial.print("Temperatura minima desde FPGA: ");
    Serial.println(tempMinimaFpga);

    Serial.print("Temperatura media desde FPGA: ");
    Serial.println(tempMediaFpga);

    Serial.print("Humedad desde FPGA: ");
    Serial.println(humedadFpga);

    Serial.println("----------------------------------------");

    return true;
  }

  Serial.println("No se han recibido los 4 bytes desde la FPGA");

  return false;
}

// =====================================================
// Enviar datos a FPGA
//
// Se envia:
//
// byte 1 = temperatura emisora 1 en BCD
// byte 2 = temperatura emisora 2 en BCD
// byte 3 = humedad en BCD
// =====================================================
void enviarAFpga(uint8_t temp1BCD,
                 uint8_t temp2BCD,
                 uint8_t humedadBCD) {

  Serial.println("----- Enviando a FPGA por UART -----");

  Serial.print("Temperatura 1 BCD enviada: 0x");
  if (temp1BCD < 0x10) Serial.print("0");
  Serial.println(temp1BCD, HEX);

  Serial.print("Temperatura 2 BCD enviada: 0x");
  if (temp2BCD < 0x10) Serial.print("0");
  Serial.println(temp2BCD, HEX);

  Serial.print("Humedad BCD enviada: 0x");
  if (humedadBCD < 0x10) Serial.print("0");
  Serial.println(humedadBCD, HEX);

  limpiarBufferFpga();

  // Primer byte: temperatura 1
  Serial1.write(temp1BCD);
  Serial1.flush();

  delay(100);

  // Segundo byte: temperatura 2
  Serial1.write(temp2BCD);
  Serial1.flush();

  delay(100);

  // Tercer byte: humedad
  Serial1.write(humedadBCD);
  Serial1.flush();

  Serial.println("Datos enviados a FPGA");
  Serial.println("-----------------------------------");
}

// =====================================================
// Imprimir MAC
// =====================================================
void imprimirMAC() {
  uint8_t mac[6];
  esp_read_mac(mac, ESP_MAC_WIFI_STA);

  Serial.print("MAC real de esta ESP32 receptora: ");

  for (int i = 0; i < 6; i++) {
    if (mac[i] < 16) Serial.print("0");
    Serial.print(mac[i], HEX);
    if (i < 5) Serial.print(":");
  }

  Serial.println();
}

// =====================================================
// Procesar paquete recibido por ESP-NOW
// =====================================================
void procesarPaquete(struct_message datos) {
  Serial.println("Paquete recibido por ESP-NOW");

  Serial.print("ID recibido: ");
  Serial.println(datos.id);

  Serial.print("Temperatura recibida: ");
  Serial.println(datos.temperatura);

  Serial.print("Humedad recibida: ");
  Serial.println(datos.humedad);

  if (datos.id == 1) {
    temp1 = datos.temperatura;
    humedad1 = datos.humedad;

    temp1Recibida = true;
    humedadRecibida = true;

    Serial.println("Datos actualizados de ESP32 emisora 1");
  }
  else if (datos.id == 2) {
    temp2 = datos.temperatura;

    temp2Recibida = true;

    Serial.println("Datos actualizados de ESP32 emisora 2");
  }
  else {
    Serial.println("ID desconocido, paquete ignorado");
    return;
  }

  if (!temp1Recibida || !temp2Recibida || !humedadRecibida) {
    Serial.println("Todavia no tengo todos los datos necesarios");
    return;
  }

  // Conversion de los datos originales a BCD
  uint8_t temp1BCD    = decimalToBCD(temp1);
  uint8_t temp2BCD    = decimalToBCD(temp2);
  uint8_t humedadBCD  = decimalToBCD(humedad1);

  Serial.println("----- Datos preparados para FPGA -----");

  Serial.print("Temperatura ESP32 1: ");
  Serial.println(temp1);

  Serial.print("Temperatura ESP32 2: ");
  Serial.println(temp2);

  Serial.print("Humedad: ");
  Serial.println(humedad1);

  Serial.println("--------------------------------------");

  // =====================================================
  // 1. Enviar los tres datos originales a la FPGA
  // =====================================================
  enviarAFpga(temp1BCD,
              temp2BCD,
              humedadBCD);

  // =====================================================
  // 2. Esperar los cuatro resultados calculados por FPGA
  // =====================================================
  uint8_t temperaturaMaximaFpga = 0;
  uint8_t temperaturaMinimaFpga = 0;
  uint8_t temperaturaMediaFpga = 0;
  uint8_t humedadFpga = 0;

  bool respuestaFpga = recibirDesdeFpga(
      temperaturaMaximaFpga,
      temperaturaMinimaFpga,
      temperaturaMediaFpga,
      humedadFpga
  );

  // =====================================================
  // 3. Enviar a ThingsBoard solo los datos devueltos
  //    por la FPGA
  // =====================================================
  if (respuestaFpga) {

    enviarAThingsBoard(
        temperaturaMaximaFpga,
        temperaturaMinimaFpga,
        temperaturaMediaFpga,
        humedadFpga
    );

  } else {

    Serial.println(
        "No se envia a ThingsBoard porque no hay respuesta de FPGA"
    );

  }
}

// =====================================================
// Callback ESP-NOW
// =====================================================
void onDataRecv(const esp_now_recv_info_t *info,
                const uint8_t *incomingData,
                int len) {

  if (len != sizeof(struct_message)) {
    return;
  }

  memcpy(&paquetePendiente,
         incomingData,
         sizeof(struct_message));

  hayPaqueteNuevo = true;
}

// =====================================================
// Setup
// =====================================================
void setup() {
  Serial.begin(115200);
  delay(3000);

  Serial.println();
  Serial.println("Iniciando ESP32 receptora...");

  // UART FPGA
  Serial1.begin(115200, SERIAL_8N1, RXD, TXD);

  Serial.println("UART hacia FPGA iniciada");
  Serial.println("RXD ESP32 = GPIO16");
  Serial.println("TXD ESP32 = GPIO17");

  // WiFi + ThingsBoard
  conectarWiFi();

  imprimirMAC();

  conectarThingsBoard();

  // ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error inicializando ESP-NOW");
    return;
  }

  esp_now_register_recv_cb(onDataRecv);

  Serial.println("ESP32 receptora lista");
}

// =====================================================
// Loop
// =====================================================
void loop() {
  if (!mqtt.connected()) {
    conectarThingsBoard();
  }

  mqtt.loop();

  if (hayPaqueteNuevo) {
    hayPaqueteNuevo = false;

    struct_message datos;

    memcpy(&datos,
           &paquetePendiente,
           sizeof(struct_message));

    procesarPaquete(datos);
  }
}