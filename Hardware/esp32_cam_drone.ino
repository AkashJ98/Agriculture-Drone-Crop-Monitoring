// ESP32-CAM (AI-Thinker) - live stream on :81/stream, photo on :80/capture
#include "esp_camera.h"
#include <WiFi.h>
#include "esp_http_server.h"
const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";
#define PWDN_GPIO_NUM 32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 0
#define SIOD_GPIO_NUM 26
#define SIOC_GPIO_NUM 27
#define Y9_GPIO_NUM 35
#define Y8_GPIO_NUM 34
#define Y7_GPIO_NUM 39
#define Y6_GPIO_NUM 36
#define Y5_GPIO_NUM 21
#define Y4_GPIO_NUM 19
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM 23
#define PCLK_GPIO_NUM 22

static esp_err_t capture_handler(httpd_req_t *req) {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) { httpd_resp_send_500(req); return ESP_FAIL; }
  httpd_resp_set_type(req, "image/jpeg");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  esp_err_t r = httpd_resp_send(req, (const char *)fb->buf, fb->len);
  esp_camera_fb_return(fb);
  return r;
}
static esp_err_t stream_handler(httpd_req_t *req) {
  httpd_resp_set_type(req, "multipart/x-mixed-replace;boundary=frame");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  char part[80];
  while (true) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) return ESP_FAIL;
    size_t n = snprintf(part, 80, "--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n", fb->len);
    esp_err_t r = httpd_resp_send_chunk(req, part, n);
    if (r == ESP_OK) r = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
    if (r == ESP_OK) r = httpd_resp_send_chunk(req, "\r\n", 2);
    esp_camera_fb_return(fb);
    if (r != ESP_OK) break;
  }
  return ESP_OK;
}
void setup() {
  Serial.begin(115200);
  camera_config_t c;
  c.ledc_channel = LEDC_CHANNEL_0; c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = Y2_GPIO_NUM; c.pin_d1 = Y3_GPIO_NUM; c.pin_d2 = Y4_GPIO_NUM; c.pin_d3 = Y5_GPIO_NUM;
  c.pin_d4 = Y6_GPIO_NUM; c.pin_d5 = Y7_GPIO_NUM; c.pin_d6 = Y8_GPIO_NUM; c.pin_d7 = Y9_GPIO_NUM;
  c.pin_xclk = XCLK_GPIO_NUM; c.pin_pclk = PCLK_GPIO_NUM; c.pin_vsync = VSYNC_GPIO_NUM; c.pin_href = HREF_GPIO_NUM;
  c.pin_sscb_sda = SIOD_GPIO_NUM; c.pin_sscb_scl = SIOC_GPIO_NUM; c.pin_pwdn = PWDN_GPIO_NUM; c.pin_reset = RESET_GPIO_NUM;
  c.xclk_freq_hz = 20000000; c.pixel_format = PIXFORMAT_JPEG; c.frame_size = FRAMESIZE_VGA;
  c.jpeg_quality = 12; c.fb_count = 2;
  if (esp_camera_init(&c) != ESP_OK) { Serial.println("Camera init failed"); return; }
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) { delay(400); Serial.print("."); }
  httpd_handle_t h1 = NULL, h2 = NULL;
  httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
  httpd_uri_t cap = {"/capture", HTTP_GET, capture_handler, NULL};
  httpd_uri_t str = {"/stream", HTTP_GET, stream_handler, NULL};
  cfg.server_port = 80;
  if (httpd_start(&h1, &cfg) == ESP_OK) httpd_register_uri_handler(h1, &cap);
  cfg.server_port = 81; cfg.ctrl_port += 1;
  if (httpd_start(&h2, &cfg) == ESP_OK) httpd_register_uri_handler(h2, &str);
  Serial.println(); Serial.print("Camera address for the dashboard: "); Serial.println(WiFi.localIP());
}
void loop() { delay(10000); }
