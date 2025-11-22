#include <Arduino.h>
#include "DHT.h"
#include <OneWire.h>
#include <DallasTemperature.h>
#include <WiFi.h>
#include <HTTPClient.h>

const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASS = "";
const char* THINGSPEAK_API_KEY = "87NUVB4VS6R94DIU";

float exampleData[][8] = {
  {32.0,43.7,20.3,21.0,22365.0,11.7,9.0,7.0},
  {25.0,45.8,20.1,20.7,40040.0,11.7,8.7,6.6},
  {18.0,60.1,27.3,19.7,14752.0,14.0,10.0,8.7},
  {18.0,69.3,29.0,19.8,30016.0,14.9,9.9,8.3},
  {25.0,46.5,18.4,20.9,40942.0,12.8,8.7,6.9},
  {27.3,53.3,19.6,20.6,743.0,11.9,8.6,6.7},
  {28.0,51.5,21.3,20.4,715.0,12.7,8.9,7.0},
  {18.0,63.5,25.4,19.6,36586.0,13.4,10.0,8.9},
  {26.9,43.2,20.0,20.3,0.0,12.5,8.9,7.4},
  {29.6,52.0,21.1,20.8,5863.0,12.6,8.2,6.3},
  {25.0,48.2,21.2,20.1,6660.0,12.1,8.6,6.5},
  {18.0,61.7,26.4,19.5,31041.0,15.1,10.0,8.8},
  {18.0,54.2,28.9,19.9,5153.0,15.4,10.0,7.7},
  {18.0,65.7,29.1,19.8,5292.0,15.1,10.0,8.7},
  {30.0,20.5,14.3,26.4,21427.0,10.5,7.7,6.0},
  {25.0,52.7,19.4,20.3,3209.0,12.1,8.1,6.7},
  {18.0,60.3,28.9,19.7,28480.0,13.7,10.0,8.4},
  {25.0,52.3,20.7,20.5,45649.0,12.2,7.8,6.6},
  {29.4,42.6,19.8,20.7,2949.0,12.9,9.0,6.5},
  {38.3,28.1,11.4,27.1,26823.0,9.0,6.6,6.1},
  {38.4,29.3,10.9,26.2,32140.0,10.7,8.9,6.1},
  {30.0,29.6,5.5,25.6,11566.0,10.7,7.0,4.7},
  {25.0,46.5,18.8,20.8,2694.0,13.5,8.7,6.1},
  {21.8,63.2,27.9,20.3,36740.0,13.6,10.0,8.3},
  {37.0,30.9,12.4,25.9,36087.0,11.4,8.6,5.7},
  {23.5,64.1,29.7,20.4,29597.0,13.8,9.4,8.0},
  {25.0,52.9,19.4,20.1,17445.0,12.2,8.2,6.6},
  {25.0,45.1,21.1,20.6,3266.0,12.7,8.5,6.5}
};

int dataIndex = 0;
int totalExamples = 30;

#define DHTPIN 32         
#define DHTTYPE DHT22
#define LDR_PIN 34         
#define SOIL_POT_PIN 35    
#define DS18B20_PIN 13     
#define N_POT_PIN 33     
#define P_POT_PIN 25    
#define K_POT_PIN 26 

DHT dht(DHTPIN, DHTTYPE);
OneWire oneWire(DS18B20_PIN);
DallasTemperature sensors(&oneWire);

float analogToPercent(int raw) {
  return (raw / 4095.0f) * 100.0f;
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("Initializing sensors...");
  dht.begin();
  sensors.begin();

  // Connect to WiFi
  Serial.print("Connecting to WiFi...");
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected!");
}

void loop() {
  float tempAir = exampleData[dataIndex][0];
  float hum = exampleData[dataIndex][1];
  float soilPercent = exampleData[dataIndex][2];
  float soilTempC = exampleData[dataIndex][3];
  float ldrPercent = exampleData[dataIndex][4];
  float nVal = exampleData[dataIndex][5];
  float pVal = exampleData[dataIndex][6];
  float kVal = exampleData[dataIndex][7];

  Serial.println("\n====== SENSOR READINGS ======");
  Serial.printf("AirTemp: %.2f °C | AirHum: %.2f %%\n", tempAir, hum);
  Serial.printf("Soil Moisture: %.1f %% | SoilTemp: %.2f °C | Light: %.1f %%\n",
              soilPercent, soilTempC, ldrPercent);
  Serial.printf("N: %.1f ppm | P: %.1f ppm | K: %.1f ppm\n", nVal, pVal, kVal);
  Serial.printf("Data example: %d/%d\n", dataIndex + 1, totalExamples);

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    String url = "https://api.thingspeak.com/update?api_key=" + String(THINGSPEAK_API_KEY) +
                 "&field1=" + String(tempAir) +
                 "&field2=" + String(hum) +
                 "&field3=" + String(soilPercent) +
                 "&field4=" + String(soilTempC) +
                 "&field5=" + String(ldrPercent) +
                 "&field6=" + String(nVal) +
                 "&field7=" + String(pVal) +
                 "&field8=" + String(kVal);

    http.begin(url);
    int code = http.GET();
    if (code > 0) {
      Serial.printf("Data sent to ThingSpeak! HTTP code: %d\n", code);
    } else {
      Serial.printf("Failed to send data. Error: %d\n", code);
    }
    http.end();
  } else {
    Serial.println("WiFi not connected!");
  }

  dataIndex = (dataIndex + 1) % totalExamples;

  delay(15000);
}