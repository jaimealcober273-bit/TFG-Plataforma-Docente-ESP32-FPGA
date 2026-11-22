#include <WiFi.h>
#include <esp_now.h>
#include <DHT.h>

#define DHTPIN 0        // Cambia esto si tu DHT11 está en otro GPIO
#define DHTTYPE DHT11

DHT dht(DHTPIN, DHTTYPE);

#include "receiver_mac.h"  // Copiar receiver_mac.example.h y configurar MAC real

typedef struct struct_message {
  uint8_t id;           // 1 = emisora 1
  uint8_t temperatura;
  uint8_t humedad;
} struct_message;

struct_message datosEnviar;

esp_now_peer_info_t peerInfo;

void onDataSent(const wifi_tx_info_t *tx_info, esp_now_send_status_t status) {
  Serial.print("Estado envio: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Correcto" : "Error");
}

void setup() {
  Serial.begin(115200);
  delay(3000);

  Serial.println();
  Serial.println("Iniciando ESP32 emisora 1 con DHT11...");

  dht.begin();
  delay(2000);

  WiFi.mode(WIFI_STA);
  delay(1000);

  Serial.print("MAC de esta ESP32 emisora 1: ");
  Serial.println(WiFi.macAddress());

  if (esp_now_init() != ESP_OK) {
    Serial.println("Error inicializando ESP-NOW");
    return;
  }

  esp_now_register_send_cb(onDataSent);

  memset(&peerInfo, 0, sizeof(peerInfo));
  memcpy(peerInfo.peer_addr, receiverAddress, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;

  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Error añadiendo peer");
    return;
  }

  Serial.println("ESP32 emisora 1 lista");
}

void loop() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();  // Celsius

  if (isnan(h) || isnan(t)) {
    Serial.println("Error leyendo DHT11");
    delay(2500);
    return;
  }

  datosEnviar.id = 1;
  datosEnviar.temperatura = (uint8_t)t;
  datosEnviar.humedad = (uint8_t)h;

  Serial.print("ID emisor: ");
  Serial.println(datosEnviar.id);

  Serial.print("Temperatura DHT11: ");
  Serial.print(t);
  Serial.print(" C -> enviada como: ");
  Serial.println(datosEnviar.temperatura);

  Serial.print("Humedad DHT11: ");
  Serial.print(h);
  Serial.print(" % -> enviada como: ");
  Serial.println(datosEnviar.humedad);

  esp_err_t result = esp_now_send(receiverAddress, (uint8_t *)&datosEnviar, sizeof(datosEnviar));

  if (result == ESP_OK) {
    Serial.println("Orden de envio lanzada");
  } else {
    Serial.println("Error al lanzar envio");
  }

  delay(2500);
}