#include <WiFi.h>
#include <esp_now.h>

#define LM35_PIN 34

#include "receiver_mac.h"

typedef struct struct_message {
  uint8_t id;
  uint8_t temperatura;
  uint8_t humedad;
} struct_message;

struct_message datosEnviar;
esp_now_peer_info_t peerInfo;

float ultimoADC = 0;
float ultimoVoltaje = 0;
float ultimaTemperatura = 0;

void onDataSent(const wifi_tx_info_t *tx_info, esp_now_send_status_t status) {
  Serial.print("Estado envio ESP-NOW: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Correcto" : "Error");
}

float leerTemperaturaLM35() {
  const int muestras = 20;
  uint32_t suma = 0;

  for (int i = 0; i < muestras; i++) {
    suma += analogRead(LM35_PIN);
    delay(5);
  }

  ultimoADC = suma / (float)muestras;

  ultimoVoltaje = ultimoADC * (3.3 / 4095.0);

  // LM35: 10 mV por grado Celsius
  ultimaTemperatura = ultimoVoltaje * 100.0;

  return ultimaTemperatura;
}

void setup() {
  Serial.begin(115200);
  delay(3000);

  Serial.println();
  Serial.println("ESP32 emisora 2 con LM35");

  pinMode(LM35_PIN, INPUT);

  analogReadResolution(12);
  analogSetPinAttenuation(LM35_PIN, ADC_11db);

  WiFi.mode(WIFI_STA);
  delay(1000);

  Serial.print("MAC de esta ESP32 emisora 2: ");
  Serial.println(WiFi.macAddress());

  if (esp_now_init() != ESP_OK) {
    Serial.println("ERROR: no se pudo inicializar ESP-NOW");
    return;
  }

  esp_now_register_send_cb(onDataSent);

  memset(&peerInfo, 0, sizeof(peerInfo));
  memcpy(peerInfo.peer_addr, receiverAddress, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;

  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("ERROR: no se pudo anadir el peer receptor");
    return;
  }

  Serial.println("ESP32 emisora 2 lista");
  Serial.println();
}

void loop() {
  float tempLM35 = leerTemperaturaLM35();

  if (tempLM35 < 0) {
    tempLM35 = 0;
  }

  if (tempLM35 > 99) {
    tempLM35 = 99;
  }

  datosEnviar.id = 2;
  datosEnviar.temperatura = (uint8_t)(tempLM35 + 0.5);
  datosEnviar.humedad = 0;

  Serial.println("---------- Lectura LM35 ----------");

  Serial.print("ADC medio: ");
  Serial.println(ultimoADC);

  Serial.print("Voltaje LM35: ");
  Serial.print(ultimoVoltaje, 3);
  Serial.println(" V");

  Serial.print("Temperatura calculada: ");
  Serial.print(ultimaTemperatura, 2);
  Serial.println(" C");

  Serial.print("Temperatura enviada: ");
  Serial.println(datosEnviar.temperatura);

  Serial.print("Humedad enviada: ");
  Serial.println(datosEnviar.humedad);

  Serial.print("ID emisor: ");
  Serial.println(datosEnviar.id);

  esp_err_t result = esp_now_send(
    receiverAddress,
    (uint8_t *)&datosEnviar,
    sizeof(datosEnviar)
  );

  if (result == ESP_OK) {
    Serial.println("Orden de envio lanzada correctamente");
  } else {
    Serial.println("ERROR: fallo al lanzar el envio");
  }

  Serial.println("----------------------------------");
  Serial.println();

  delay(2500);
}
