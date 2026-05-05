#define CAMERA_MODEL_ESP32S3_EYE
#include "camera_pins.h"
#include <WiFi.h>
#include <WebSocketsClient.h>
#include "esp_camera.h"
#include "wifiConfig.h"

const char* ws_host = "192.168.0.103";
const int ws_port = 8000;
const char* ws_path = "/ws/cam";

#define BUTTON_PIN 14

WebSocketsClient webSocket;

bool isSending = false;
bool unlocked = false;

void startCamera() {
  camera_config_t config;

  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;

  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;

  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;

  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;

  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;

  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  config.frame_size = FRAMESIZE_QVGA;
  config.jpeg_quality = 12;
  config.fb_count = 1;
  
  config.grab_mode = CAMERA_GRAB_LATEST; 

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }

  Serial.println("Camera OK");
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  if (type == WStype_TEXT) {
    String msg = (char*)payload;
    Serial.println(msg);

    if (msg.indexOf("unlock") >= 0) {
      unlocked = true;
    }
  }
}

void sendFrames() {
  Serial.println("SEND START");

  // ✅ SỬA LỖI: Chủ động "xả" 1 frame cũ đang kẹt trong ống kính trước khi gửi
  camera_fb_t * dummy_fb = esp_camera_fb_get();
  if (dummy_fb) {
    esp_camera_fb_return(dummy_fb);
  }

  webSocket.sendTXT("{\"key\":\"abc123\",\"max_frames\":5,\"similarity_threshold\":70}");

  for (int i = 0; i < 6; i++) {
    webSocket.loop();

    if (unlocked) break;

    camera_fb_t * fb = esp_camera_fb_get();
    if (!fb) continue;

    webSocket.sendBIN(fb->buf, fb->len);

    Serial.print("Frame: ");
    Serial.println(fb->len);

    esp_camera_fb_return(fb);

    delay(80);
  }

  Serial.println("SEND DONE");
}

void setup() {
  Serial.begin(115200);

  wifiConfig.begin();   // khởi tạo wifi + web config
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  startCamera();
  webSocket.begin(ws_host, ws_port, ws_path);
  webSocket.onEvent(webSocketEvent);
}

void loop() {
  wifiConfig.run();

  if (WiFi.status() == WL_CONNECTED) {
    webSocket.loop();
  }
  
  if (digitalRead(BUTTON_PIN) == LOW && !isSending) {
    delay(50); 

    if (digitalRead(BUTTON_PIN) == LOW) {
      Serial.println("BUTTON");

      isSending = true;
      unlocked = false;

      sendFrames();

      isSending = false;

      while (digitalRead(BUTTON_PIN) == LOW) {
        webSocket.loop();
        delay(10);
      }
    }
  }
}