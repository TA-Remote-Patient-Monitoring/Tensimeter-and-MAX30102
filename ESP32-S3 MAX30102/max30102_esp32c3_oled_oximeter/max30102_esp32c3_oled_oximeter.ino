#include <Arduino.h>
#include <U8g2lib.h>
#include <Wire.h>
#include "algorithm_by_RF.h"
#include "max30102.h"
#include "algorithm.h" 
#include "median_filter.h"
#include <WiFi.h>
#include <HTTPClient.h>

// ========== KONFIGURASI WIFI & BACKEND ==========
const char* ssid = "Twenty Three House 4G";
const char* password = "HouseOf23";
const char* server_url = "http://rpms.gilangramadhani.tech/api/measurements/spo2";

// ID User dan Profile TIDAK perlu di-hardcode lagi.
// Backend akan otomatis resolve dari "active session"
// yang di-set oleh Expo app saat user klik "Mau Prediksi Gula Darah?"
// ================================================

// Interrupt pin
// const byte oxiInt = 2; // (Tidak digunakan)
const int SENSOR_I2C_SDA_PIN = 8;
const int SENSOR_I2C_SCL_PIN = 9;
const int OLED_SDA_PIN = 4;  // Pin SDA khusus OLED (terpisah dari sensor)
const int OLED_SCL_PIN = 5;  // Pin SCL khusus OLED (terpisah dari sensor)
const int HEARTBEAT_LED_PIN = 10; // Dipindah ke 10 agar tidak bentrok dengan SDA(8)
const uint32_t HEARTBEAT_LED_PULSE_MS = 60;
const bool HEARTBEAT_LED_ACTIVE_LOW = true;

uint32_t elapsedTime,timeStart;

uint32_t aun_ir_buffer[BUFFER_SIZE]; // Infrared ring buffer.
uint32_t aun_red_buffer[BUFFER_SIZE];  // Red ring buffer.
uint32_t ordered_ir_buffer[BUFFER_SIZE]; // Oldest-to-newest IR view for algorithms.
uint32_t ordered_red_buffer[BUFFER_SIZE]; // Oldest-to-newest RED view for algorithms.
const int32_t UPDATE_STEP = 10; // New samples per update; keep <= BUFFER_SIZE.
const uint8_t MEDIAN_HISTORY = 4; // Number of previous samples kept for median filtering.
const int32_t INVALID_HR = -999;
const float INVALID_SPO2 = -999.0f;
uint16_t sample_write_index = 0;
uint16_t sample_count = 0;

MedianFilter<int32_t, MEDIAN_HISTORY> hr_filter(INVALID_HR);
MedianFilter<float, MEDIAN_HISTORY> spo2_filter(INVALID_SPO2);
uint32_t next_heartbeat_flash_ms = 0;
uint32_t heartbeat_led_off_ms = 0;
bool heartbeat_led_on = false;

// Variables for 10-second stability check
uint32_t stable_start_time = 0;
bool is_stable = false;
bool data_sent = false;
bool wifi_connected = false; // Status WiFi global

// ========== KONFIGURASI & STATES OLED ==========
enum DisplayState {
  STATE_CONNECTING_WIFI,
  STATE_WIFI_CONNECTED,
  STATE_SENSOR_ERROR,
  STATE_NO_FINGER,
  STATE_MEASURING,
  STATE_SENDING,
  STATE_SEND_SUCCESS,
  STATE_SEND_ERROR
};

// Driver SSD1306 128x64 menggunakan SOFTWARE I2C di pin terpisah (GPIO 4 & 5)
// Agar tidak bentrok fisik dengan MAX30102 yang sudah di GPIO 8 & 9
U8G2_SSD1306_128X64_NONAME_F_SW_I2C u8g2(U8G2_R0, /* SCL=*/ OLED_SCL_PIN, /* SDA=*/ OLED_SDA_PIN, /* reset=*/ U8X8_PIN_NONE);

int last_http_code = 0;

void drawHeader(const char* title) {
  u8g2.setFont(u8g2_font_8x13_tf);
  int w = u8g2.getStrWidth(title);
  u8g2.drawStr((128 - w) / 2, 12, title);
  u8g2.drawHLine(0, 15, 128);
}

void updateOledScreen(DisplayState state, int bpm = -1, int spo2 = -1, const String& extraInfo = "") {
  u8g2.clearBuffer();
  
  switch(state) {
    case STATE_CONNECTING_WIFI:
      drawHeader("WIFI KONEKSI");
      u8g2.setFont(u8g2_font_6x10_tf);
      u8g2.drawStr(0, 30, "Menghubungkan ke:");
      u8g2.drawStr(0, 43, ssid);
      u8g2.drawStr(0, 58, "Harap tunggu...");
      break;

    case STATE_WIFI_CONNECTED:
      drawHeader("WIFI TERHUBUNG");
      u8g2.setFont(u8g2_font_6x10_tf);
      u8g2.drawStr(0, 30, "Terhubung!");
      u8g2.drawStr(0, 43, ("IP: " + WiFi.localIP().toString()).c_str());
      u8g2.drawStr(0, 58, "Memulai sensor...");
      break;

    case STATE_SENSOR_ERROR:
      drawHeader("SENSOR ERROR");
      u8g2.setFont(u8g2_font_6x10_tf);
      u8g2.drawStr(0, 32, "Sensor MAX30102");
      u8g2.drawStr(0, 45, "tidak terdeteksi!");
      u8g2.drawStr(0, 58, "Cek kabel & pin");
      break;

    case STATE_NO_FINGER:
      drawHeader("READY STATE");
      u8g2.setFont(u8g2_font_6x10_tf);
      u8g2.drawStr(15, 34, "Tempelkan Jari");
      u8g2.drawStr(15, 48, "Untuk Mengukur");
      u8g2.drawStr(0, 62, "WiFi: Terhubung");
      break;

    case STATE_MEASURING:
      drawHeader("MENGAMBIL DATA");
      
      u8g2.setFont(u8g2_font_6x10_tf);
      u8g2.drawStr(5, 30, "BPM :");
      u8g2.setFont(u8g2_font_10x20_tr);
      if (bpm >= 30 && bpm <= 220) {
        u8g2.setCursor(45, 33);
        u8g2.print(bpm);
      } else {
        u8g2.drawStr(45, 33, "--");
      }
      
      u8g2.setFont(u8g2_font_6x10_tf);
      u8g2.drawStr(5, 52, "SpO2:");
      u8g2.setFont(u8g2_font_10x20_tr);
      if (spo2 >= 50 && spo2 <= 100) {
        u8g2.setCursor(45, 55);
        u8g2.print(spo2);
        u8g2.print(" %");
      } else {
        u8g2.drawStr(45, 55, "-- %");
      }
      
      u8g2.setFont(u8g2_font_6x10_tf);
      if (extraInfo != "") {
        u8g2.drawStr(5, 62, extraInfo.c_str());
      } else {
        u8g2.drawStr(5, 62, "Mencari sinyal...");
      }
      break;

    case STATE_SENDING:
      drawHeader("MENGIRIM DATA");
      
      u8g2.setFont(u8g2_font_6x10_tf);
      u8g2.drawStr(5, 28, "BPM :");
      u8g2.setFont(u8g2_font_10x20_tr);
      u8g2.setCursor(45, 31);
      u8g2.print(bpm);
      
      u8g2.setFont(u8g2_font_6x10_tf);
      u8g2.drawStr(5, 48, "SpO2:");
      u8g2.setFont(u8g2_font_10x20_tr);
      u8g2.setCursor(45, 51);
      u8g2.print(spo2);
      u8g2.print(" %");
      
      u8g2.setFont(u8g2_font_6x10_tf);
      u8g2.drawStr(5, 62, "Mengirim ke server...");
      break;

    case STATE_SEND_SUCCESS:
      drawHeader("DATA TERKIRIM");
      
      u8g2.setFont(u8g2_font_6x10_tf);
      u8g2.drawStr(5, 28, "BPM :");
      u8g2.setFont(u8g2_font_10x20_tr);
      u8g2.setCursor(45, 31);
      u8g2.print(bpm);
      
      u8g2.setFont(u8g2_font_6x10_tf);
      u8g2.drawStr(5, 48, "SpO2:");
      u8g2.setFont(u8g2_font_10x20_tr);
      u8g2.setCursor(45, 51);
      u8g2.print(spo2);
      u8g2.print(" %");
      
      u8g2.setFont(u8g2_font_6x10_tf);
      u8g2.drawStr(5, 62, "Terkirim ke Server!");
      break;

    case STATE_SEND_ERROR:
      drawHeader("GAGAL MENGIRIM");
      
      u8g2.setFont(u8g2_font_6x10_tf);
      u8g2.drawStr(5, 28, "BPM :");
      u8g2.setFont(u8g2_font_10x20_tr);
      u8g2.setCursor(45, 31);
      u8g2.print(bpm);
      
      u8g2.setFont(u8g2_font_6x10_tf);
      u8g2.drawStr(5, 48, "SpO2:");
      u8g2.setFont(u8g2_font_10x20_tr);
      u8g2.setCursor(45, 51);
      u8g2.print(spo2);
      u8g2.print(" %");
      
      u8g2.setFont(u8g2_font_6x10_tf);
      u8g2.drawStr(5, 62, ("Err: " + extraInfo).c_str());
      break;
  }
  
  u8g2.sendBuffer();
}
// ================================================

void sendToDashboard(float spo2, float bpm, float temp) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(server_url);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-Service-Key", "fCpTkSJvTydNIAGnh68NlSUbH3tLZ-jFAL2Jq-e173g");

    // Tanpa id_user & id_profile — backend resolve dari active session
    String jsonPayload = "{";
    jsonPayload += "\"spo2\":" + String(spo2, 1) + ",";
    jsonPayload += "\"bpm\":" + String(bpm, 1) + ",";
    jsonPayload += "\"temperature\":" + String(temp, 2);
    jsonPayload += "}";

    // Perbarui layar ke status MENGIRIM
    updateOledScreen(STATE_SENDING, (int)bpm, (int)spo2);

    int httpResponseCode = http.POST(jsonPayload);
    last_http_code = httpResponseCode;
    if (httpResponseCode > 0) {
      Serial.print("Data dikirim ke Dashboard! HTTP Response: ");
      Serial.println(httpResponseCode);
      Serial.println(http.getString());
      updateOledScreen(STATE_SEND_SUCCESS, (int)bpm, (int)spo2);
    } else {
      Serial.print("Error saat mengirim POST: ");
      Serial.println(httpResponseCode);
      updateOledScreen(STATE_SEND_ERROR, (int)bpm, (int)spo2, "HTTP " + String(httpResponseCode));
    }
    http.end();
  } else {
    Serial.println("WiFi terputus, tidak bisa mengirim data.");
    last_http_code = -99;
    updateOledScreen(STATE_SEND_ERROR, (int)bpm, (int)spo2, "No WiFi");
  }
}

static void setHeartbeatLed(bool on) {
  const int level = (on ^ HEARTBEAT_LED_ACTIVE_LOW) ? HIGH : LOW;
  digitalWrite(HEARTBEAT_LED_PIN, level);
}

static void waitForDataReady(uint32_t timeout_us) {
  uint32_t wait_start = micros();
  uint8_t status = 0;
  // Polling via I2C karena pin INT tidak dihubungkan
  while(true) {
    maxim_max30102_read_reg(0x00, &status); // REG_INTR_STATUS_1
    if ((status & 0x40) != 0) break; // 0x40 is PPG_RDY
    if((micros()-wait_start) > timeout_us) {
      // Serial.println("Given up on IR");
      break;
    }
    delayMicroseconds(500);
  }
}

static void readNextSampleIntoRing(uint32_t timeout_us) {
  waitForDataReady(timeout_us);
  maxim_max30102_read_fifo(&aun_red_buffer[sample_write_index], &aun_ir_buffer[sample_write_index]);
  sample_write_index = (sample_write_index + 1) % BUFFER_SIZE;
  if(sample_count < BUFFER_SIZE) ++sample_count;
}

static void buildOrderedWindow() {
  // Next write index always points at the oldest sample in a full ring.
  uint16_t start = sample_write_index;
  for(uint16_t i=0; i<BUFFER_SIZE; ++i) {
    uint16_t src = (start + i) % BUFFER_SIZE;
    ordered_red_buffer[i] = aun_red_buffer[src];
    ordered_ir_buffer[i] = aun_ir_buffer[src];
  }
}

static void updateHeartbeatLed(int32_t hr_bpm) {
  const uint32_t now_ms = millis();

  if(heartbeat_led_on && now_ms >= heartbeat_led_off_ms) {
    setHeartbeatLed(false);
    heartbeat_led_on = false;
  }

  // Keep blink output tied to plausible heart-rate values.
  if(hr_bpm < 35 || hr_bpm > 220) {
    next_heartbeat_flash_ms = 0;
    return;
  }

  const uint32_t beat_period_ms = 60000UL / (uint32_t)hr_bpm;
  if(next_heartbeat_flash_ms == 0) {
    next_heartbeat_flash_ms = now_ms;
  }

  if(now_ms >= next_heartbeat_flash_ms) {
    setHeartbeatLed(true);
    heartbeat_led_on = true;
    heartbeat_led_off_ms = now_ms + HEARTBEAT_LED_PULSE_MS;
    next_heartbeat_flash_ms = now_ms + beat_period_ms;
  }
}

void setup() {
  // pinMode(oxiInt, INPUT);
  pinMode(HEARTBEAT_LED_PIN, OUTPUT);
  setHeartbeatLed(false);
  Serial.begin(115200);
  delay(1000); 

  // Memulai Layar OLED
  u8g2.begin();

  // Setup WiFi dengan display status pada OLED + TIMEOUT 15 detik
  Serial.println();
  Serial.print("Menghubungkan ke WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  
  uint32_t wifi_start = millis();
  const uint32_t WIFI_TIMEOUT_MS = 15000; // 15 detik timeout
  
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - wifi_start >= WIFI_TIMEOUT_MS) {
      Serial.println("\nWiFi GAGAL terhubung (timeout 15 detik)");
      updateOledScreen(STATE_SEND_ERROR, -1, -1, "WiFi Timeout");
      delay(2000);
      wifi_connected = false;
      break;
    }
    int elapsed_sec = (millis() - wifi_start) / 1000;
    updateOledScreen(STATE_CONNECTING_WIFI);
    delay(500);
    Serial.print(".");
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    wifi_connected = true;
    Serial.println("\nWiFi Terhubung!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    updateOledScreen(STATE_WIFI_CONNECTED);
    delay(1500);
  }

  // Inisialisasi sensor MAX30102 dengan deteksi error
  if (!maxim_max30102_init(SENSOR_I2C_SDA_PIN, SENSOR_I2C_SCL_PIN)) {
    Serial.println("Gagal mendeteksi sensor MAX30102!");
    while(true) {
      updateOledScreen(STATE_SENSOR_ERROR);
      delay(1000);
    }
  }

  Serial.print(F("Time[s]\tSpO2\tHR\tSpO2_MX\tHR_MX\tClock\tRatio\tCorr\tTemp[C]"));
  Serial.println("");

  timeStart=millis();
}

static void updateDisplay(int32_t hr, int32_t spo2) {
  // Fungsi ini kini digantikan oleh updateOledScreen() yang lebih lengkap
}


//Continuously taking samples from MAX30102.  Heart rate and SpO2 are calculated every ST seconds
void loop() {
  // ========== AUTO-RECONNECT WIFI ==========
  if (WiFi.status() != WL_CONNECTED) {
    if (wifi_connected) {
      // WiFi baru saja putus
      wifi_connected = false;
      Serial.println("WiFi terputus! Mencoba reconnect...");
    }
    // Coba reconnect setiap loop tanpa blocking
    static uint32_t last_reconnect_attempt = 0;
    if (millis() - last_reconnect_attempt > 5000) { // Coba tiap 5 detik
      last_reconnect_attempt = millis();
      WiFi.disconnect();
      WiFi.begin(ssid, password);
    }
  } else if (!wifi_connected) {
    // Baru saja berhasil reconnect
    wifi_connected = true;
    Serial.println("WiFi reconnected!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
  }
  // ==========================================

  float n_spo2,ratio,correl;  //SPO2 value
  int8_t ch_spo2_valid;  //indicator to show if the SPO2 calculation is valid
  int32_t n_heart_rate; //heart rate value
  int8_t  ch_hr_valid;  //indicator to show if the heart rate calculation is valid
  int32_t filtered_heart_rate;
  float filtered_spo2;
  char hr_str[10];
  const uint32_t data_ready_timeout_us = (2000000UL / FS); // Allow up to 2 sample periods.

  for(int32_t n=0; n<UPDATE_STEP; ++n) {
    readNextSampleIntoRing(data_ready_timeout_us);
    // Send raw IR value for real-time waveform plotting in the web GUI
    uint16_t prev_idx = (sample_write_index == 0) ? BUFFER_SIZE - 1 : sample_write_index - 1;
    // Hanya print IR jika jari nempel (IR > 50000, nilai bisa disesuaikan)
    if (aun_ir_buffer[prev_idx] > 50000) {
      Serial.print("IR:");
      Serial.println(aun_ir_buffer[prev_idx]);
    }
  }

  // Cek keberadaan jari secara real-time berdasarkan nilai IR terbaru
  uint16_t last_sample_idx = (sample_write_index == 0) ? BUFFER_SIZE - 1 : sample_write_index - 1;
  bool finger_detected = (aun_ir_buffer[last_sample_idx] > 50000);

  if (!finger_detected) {
    is_stable = false;
    data_sent = false;
    last_http_code = 0;
    updateOledScreen(STATE_NO_FINGER);
    sample_count = 0; // Reset agar saat jari ditempelkan lagi, buffer mengisi dari awal
    return;
  }

  // Tampilkan progress pengisian buffer di layar OLED jika buffer belum penuh
  if(sample_count < BUFFER_SIZE) {
    int progress = (sample_count * 100) / BUFFER_SIZE;
    updateOledScreen(STATE_MEASURING, -1, -1, "Inisialisasi: " + String(progress) + "%");
    return;
  }

  buildOrderedWindow();

  //calculate heart rate and SpO2 after BUFFER_SIZE samples (ST seconds of samples) using Robert's method
  rf_heart_rate_and_oxygen_saturation(ordered_ir_buffer, BUFFER_SIZE, ordered_red_buffer, &n_spo2, &ch_spo2_valid, &n_heart_rate, &ch_hr_valid, &ratio, &correl); 
  elapsedTime=millis()-timeStart;
  millis_to_hours(elapsedTime,hr_str); // Time in hh:mm:ss format
  elapsedTime/=1000; // Time in seconds

  // Read the _chip_ temperature in degrees Celsius
  int8_t integer_temperature;
  uint8_t fractional_temperature;
  maxim_max30102_read_temperature(&integer_temperature, &fractional_temperature);
  float temperature = integer_temperature + ((float)fractional_temperature)/16.0;

  //calculate heart rate and SpO2 after BUFFER_SIZE samples (ST seconds of samples) using MAXIM's method
  float n_spo2_maxim;  //SPO2 value
  int8_t ch_spo2_valid_maxim;  //indicator to show if the SPO2 calculation is valid
  int32_t n_heart_rate_maxim; //heart rate value
  int8_t  ch_hr_valid_maxim;  //indicator to show if the heart rate calculation is valid
  maxim_heart_rate_and_oxygen_saturation(ordered_ir_buffer, BUFFER_SIZE, ordered_red_buffer, &n_spo2_maxim, &ch_spo2_valid_maxim, &n_heart_rate_maxim, &ch_hr_valid_maxim); 

  filtered_heart_rate = n_heart_rate;
  filtered_spo2 = n_spo2;
  int32_t median_hr;
  float median_spo2;
  if(hr_filter.median(&median_hr)) filtered_heart_rate = median_hr;
  if(spo2_filter.median(&median_spo2)) filtered_spo2 = median_spo2;
  updateHeartbeatLed(filtered_heart_rate);

  // ========== STABILITY CHECK (10 DETIK) ==========
  bool current_valid = (ch_hr_valid && ch_spo2_valid && filtered_heart_rate > 30 && filtered_spo2 > 50.0);

  if (current_valid) {
    // Hanya print hasil kalau jari valid
    Serial.print(elapsedTime);
    Serial.print("\t");
    Serial.print(filtered_spo2);
    Serial.print("\t");
    Serial.print(filtered_heart_rate, DEC);
    Serial.print("\t");
    Serial.print(n_spo2_maxim);
    Serial.print("\t");
    Serial.print(n_heart_rate_maxim, DEC);
    Serial.print("\t");
    Serial.print(hr_str);
    Serial.print("\t");
    Serial.print(ratio);
    Serial.print("\t");
    Serial.print(correl);
    Serial.print("\t");
    Serial.print(temperature);
    Serial.println("");

    if (!is_stable) {
      is_stable = true;
      stable_start_time = millis();
      Serial.println("\n>>> JARI TERDETEKSI: Menunggu stabil selama 10 detik...");
      updateOledScreen(STATE_MEASURING, (int)filtered_heart_rate, (int)filtered_spo2, "Stabilisasi: 10s");
    } else {
      if (!data_sent) {
        int elapsed_stable = (millis() - stable_start_time) / 1000;
        int remaining = 10 - elapsed_stable;
        if (remaining < 0) remaining = 0;
        
        if (elapsed_stable >= 10) { // 10 detik berlalu
          Serial.println("\n>>> DATA STABIL: Mengirim ke server...");
          sendToDashboard(filtered_spo2, (float)filtered_heart_rate, temperature);
          data_sent = true; // Hanya kirim sekali selama jari masih nempel
        } else {
          updateOledScreen(STATE_MEASURING, (int)filtered_heart_rate, (int)filtered_spo2, "Stabil dlm: " + String(remaining) + "s");
        }
      } else {
        // Jika data sudah terkirim, tampilkan status keberhasilan/kegagalan kirim secara terus-menerus
        if (last_http_code > 0) {
          updateOledScreen(STATE_SEND_SUCCESS, (int)filtered_heart_rate, (int)filtered_spo2);
        } else {
          updateOledScreen(STATE_SEND_ERROR, (int)filtered_heart_rate, (int)filtered_spo2, "HTTP " + String(last_http_code));
        }
      }
    }
  } else {
    // Jari terdeteksi tapi data berantakan (belum valid)
    if (is_stable) {
      Serial.println("\n>>> DATA TIDAK STABIL: Reset timer.");
    }
    is_stable = false;
    data_sent = false; 
    last_http_code = 0;
    updateOledScreen(STATE_MEASURING, -1, -1, "Mencari sinyal...");
  }
  // ================================================

  hr_filter.push(ch_hr_valid ? n_heart_rate : INVALID_HR);
  spo2_filter.push(ch_spo2_valid ? n_spo2 : INVALID_SPO2);
}

void millis_to_hours(uint32_t ms, char* hr_str)
{
  char istr[6];
  uint32_t secs,mins,hrs;
  secs=ms/1000; // time in seconds
  mins=secs/60; // time in minutes
  secs-=60*mins; // leftover seconds
  hrs=mins/60; // time in hours
  mins-=60*hrs; // leftover minutes
  itoa(hrs,hr_str,10);
  strcat(hr_str,":");
  itoa(mins,istr,10);
  strcat(hr_str,istr);
  strcat(hr_str,":");
  itoa(secs,istr,10);
  strcat(hr_str,istr);
}