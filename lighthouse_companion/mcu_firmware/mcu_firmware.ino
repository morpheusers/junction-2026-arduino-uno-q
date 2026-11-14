#include <Wire.h>
#include <Arduino_LED_Matrix.h>
#include <Adafruit_BME280.h>

ArduinoLEDMatrix matrix;
Adafruit_BME280 bme;

const int PIN_CLK = 2;
const int PIN_DT  = 3;
const int PIN_SW  = 4;

int lastClkState;
unsigned long btnPressTime = 0;
bool btnHeld = false;
unsigned long lastSensorPush = 0;

uint8_t frame[8][13] = {0};

void highlightZoneOnMatrix(int zoneIdx) {
  memset(frame, 0, sizeof(frame));
  int startCol = (zoneIdx % 3) * 4;
  for (int r = 1; r < 7; r++) {
    for (int c = startCol; c < startCol + 4 && c < 13; c++) {
      frame[r][c] = 1;
    }
  }
  matrix.renderBitmap(frame, 8, 13);
}

void drawProgress(int cols) {
  memset(frame, 0, sizeof(frame));
  for (int r = 2; r < 6; r++) {
    for (int c = 0; c < cols && c < 13; c++) {
      frame[r][c] = 1;
    }
  }
  matrix.renderBitmap(frame, 8, 13);
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  matrix.begin();

  pinMode(PIN_CLK, INPUT_PULLUP);
  pinMode(PIN_DT, INPUT_PULLUP);
  pinMode(PIN_SW, INPUT_PULLUP);
  lastClkState = digitalRead(PIN_CLK);

  bme.begin(0x76);
  drawProgress(1);
}

void loop() {
  int currentClk = digitalRead(PIN_CLK);
  if (currentClk != lastClkState && currentClk == LOW) {
    if (digitalRead(PIN_DT) != currentClk) {
      Serial.println("EVENT:KNOB_RIGHT");
    } else {
      Serial.println("EVENT:KNOB_LEFT");
    }
  }
  lastClkState = currentClk;

  if (digitalRead(PIN_SW) == LOW) {
    if (btnPressTime == 0) btnPressTime = millis();
    if (!btnHeld && (millis() - btnPressTime > 1500)) {
      Serial.println("EVENT:LONG_PRESS_DEMO");
      btnHeld = true;
    }
  } else {
    if (btnPressTime > 0 && !btnHeld && (millis() - btnPressTime > 50)) {
      Serial.println("EVENT:CLICK");
    }
    btnPressTime = 0;
    btnHeld = false;
  }

  if (millis() - lastSensorPush > 2000) {
    float temp = bme.readTemperature();
    float hum  = bme.readHumidity();
    if (isnan(temp)) { temp = 22.5; hum = 55.0; }
    Serial.print("CLIMATE:");
    Serial.print(temp, 1);
    Serial.print(",");
    Serial.println(hum, 1);
    lastSensorPush = millis();
  }

  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.startsWith("ZONE:")) {
      int z = cmd.substring(5).toInt();
      highlightZoneOnMatrix(z);
    } else if (cmd.startsWith("PROG:")) {
      int p = cmd.substring(5).toInt();
      drawProgress(p);
    }
  }
}
