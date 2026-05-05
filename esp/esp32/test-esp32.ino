#include "wifiConfig.h"
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <U8g2lib.h>
#include <Wire.h>
#include <ArduinoJson.h>

// ================== PIN ==================
#define RELAY_PIN 13
#define BUZZER_PIN 12

// ================== OLED ==================
U8G2_SSD1306_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE);

// ================== WS ==================
WebSocketsClient webSocket;
const char* ws_host = "192.168.0.103";
const int ws_port = 8000;
bool isWsConnected = false; // Biến theo dõi trạng thái kết nối WebSocket

// ================== STATE ==================
enum SystemState { 
  IDLE, 
  SCANNING, 
  SUCCESS, 
  FAILED,
  NO_FACE
};

SystemState currentState = IDLE;
String recognizedName = "";
float confidenceValue = 0;

// ================== TIMER ==================
unsigned long stateTimer = 0;
const unsigned long SCAN_TIMEOUT = 5000;
int dotCount = 0;

// ================== BUZZER ==================
void beep(int times) {
  for (int i = 0; i < times; i++) {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(120);
    digitalWrite(BUZZER_PIN, LOW);
    delay(120);
  }
}

// ================== UI ==================
void updateOLED() {
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_6x10_tr);

  // 1. Vẽ khung viền và đường phân cách
  u8g2.drawFrame(0, 0, 128, 64);
  u8g2.drawLine(0, 15, 127, 15);

  // 2. In Header: Trạng thái động của WiFi & WebSocket
  String wifiStr = (WiFi.status() == WL_CONNECTED) ? "wifi: ok" : "wifi: err";
  String wsStr = isWsConnected ? "ws: ok" : "ws: err";

  u8g2.drawStr(5, 11, wifiStr.c_str());
  int wsX = 128 - 5 - u8g2.getStrWidth(wsStr.c_str());
  u8g2.drawStr(wsX, 11, wsStr.c_str());

  // 3. Nội dung hiển thị theo trạng thái 
  switch (currentState) {
    case IDLE:
      u8g2.drawStr(5, 30, "System: Ready...");
      break;

    case SCANNING: {
      String dots = "";
      for (int i = 0; i < dotCount; i++) dots += ".";
      u8g2.drawStr(5, 30, ("Scanning" + dots).c_str());
      dotCount = (dotCount + 1) % 4;
      break;
    }

    case SUCCESS: {
      u8g2.drawStr(5, 30, "Access unlock");
      u8g2.drawStr(5, 44, ("user: " + recognizedName).c_str());
      u8g2.drawStr(5, 58, ("confidence: " + String(confidenceValue, 1) + "%").c_str());
      break;
    }

    case FAILED:
      u8g2.drawStr(5, 30, "Access denied");
      u8g2.drawStr(5, 44, "user: Unknown");
      break;

    case NO_FACE:
      u8g2.drawStr(5, 30, "Status: No Face");
      break;
  }
  
  u8g2.sendBuffer();
}

// ================== WS EVENT ==================
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_CONNECTED:
      Serial.println("Connected to server");
      isWsConnected = true; // Cập nhật cờ khi kết nối thành công
      currentState = IDLE;
      updateOLED();
      break;

    case WStype_TEXT: {
      String msg = (char*)payload;
      Serial.println("Received: " + msg);

      DynamicJsonDocument doc(512);
      DeserializationError err = deserializeJson(doc, msg);

      if (err) return;

      if (doc.containsKey("unlock") && doc["unlock"] == true) {
        if (doc.containsKey("name")) recognizedName = doc["name"].as<String>();
        else recognizedName = "Unknown";

        if (doc.containsKey("confidence")) confidenceValue = doc["confidence"].as<float>();
        else confidenceValue = 0;

        currentState = SUCCESS;
        updateOLED();
        beep(1);

        digitalWrite(RELAY_PIN, HIGH);
        delay(3000);
        digitalWrite(RELAY_PIN, LOW);

        delay(2000);
        currentState = IDLE;
        updateOLED();
      }
      else if (doc.containsKey("unlock") && doc["unlock"] == false) {
        currentState = FAILED;
        updateOLED();
        beep(2);

        delay(2000);
        currentState = IDLE;
        updateOLED();
      }
      break;
    }

    case WStype_DISCONNECTED:
      Serial.println("Disconnected");
      isWsConnected = false; // Cập nhật cờ khi mất kết nối
      currentState = FAILED;
      updateOLED();
      break;
  }
}

// ================== SETUP ==================
void setup() {
  Serial.begin(115200);

  pinMode(RELAY_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);

  u8g2.begin();
  
  u8g2.clearBuffer();
  u8g2.drawFrame(0, 0, 128, 64);
  u8g2.setFont(u8g2_font_6x10_tr);
  u8g2.drawStr(35, 35, "Booting...");
  u8g2.sendBuffer();

  wifiConfig.begin();

  webSocket.begin(ws_host, ws_port, "/ws/esp?key=abc123");
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
}

// ================== LOOP ==================
void loop() {
  wifiConfig.run();
  webSocket.loop();

  // Thêm cơ chế tự làm mới màn hình định kỳ (VD: mỗi 2 giây) để cập nhật trạng thái kết nối mạng nếu có rớt mạng ngầm
  static unsigned long lastRefresh = 0;
  if (millis() - lastRefresh > 2000 && currentState != SCANNING) {
    updateOLED();
    lastRefresh = millis();
  }

  if (currentState == SCANNING) {
    if (millis() - stateTimer > SCAN_TIMEOUT) {
      Serial.println(">>> SCAN TIMEOUT -> FAILED");
      currentState = FAILED;
      updateOLED();
      beep(2);
      delay(2000);
      currentState = IDLE;
      updateOLED();
    } else {
      static unsigned long animTimer = 0;
      if (millis() - animTimer > 300) {
        updateOLED(); 
        animTimer = millis();
      }
    }
  }
}