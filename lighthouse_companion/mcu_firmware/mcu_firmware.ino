#include <Arduino_Modulino.h>
#include <Arduino_LED_Matrix.h>

ArduinoLEDMatrix matrix;

ModulinoKnob knob;
ModulinoThermo thermo;
ModulinoBuzzer buzzer;

// Momentary push-button wired between D8 and GND (internal pull-up enabled).
// D8 is a free GPIO (PB4 / TIM3_CH1) and is not shared with UART, SPI, or I2C.
const int PIN_POWER_BTN = 8;

const unsigned long KNOB_LONG_PRESS_MS  = 1500;
const unsigned long CLIMATE_INTERVAL_MS = 2000;
const unsigned long ALARM_INTERVAL_MS   = 3000;
const unsigned long POWER_DEBOUNCE_MS   = 60;

const unsigned int WATER_ALARM_FREQ_HZ = 1047;  // C6
const unsigned int WATER_ALARM_BEEP_MS = 180;

bool systemOn = true;
bool waterAlarm = false;

unsigned long knobPressTime = 0;
bool knobWasDown = false;
bool knobLongFired = false;
unsigned long lastSensorPush = 0;
unsigned long lastAlarmBeep = 0;

bool powerWasDown = false;
unsigned long powerDownTime = 0;

uint8_t frame[8][13] = {{0}};

void renderFrame() {
  matrix.renderBitmap(frame, 8, 13);
}

void clearMatrix() {
  memset(frame, 0, sizeof(frame));
  renderFrame();
}

void highlightZoneOnMatrix(int zoneIdx) {
  memset(frame, 0, sizeof(frame));
  int startCol = (zoneIdx % 3) * 4;
  for (int r = 1; r < 7; r++) {
    for (int c = startCol; c < startCol + 4 && c < 13; c++) {
      frame[r][c] = 1;
    }
  }
  renderFrame();
}

void drawProgress(int cols) {
  memset(frame, 0, sizeof(frame));
  for (int r = 2; r < 6; r++) {
    for (int c = 0; c < cols && c < 13; c++) {
      frame[r][c] = 1;
    }
  }
  renderFrame();
}

// ---------------------------------------------------------------- water alert

void startWaterAlarm() {
  waterAlarm = true;
  lastAlarmBeep = millis() - ALARM_INTERVAL_MS;  // beep immediately
}

void stopWaterAlarm() {
  waterAlarm = false;
  buzzer.noTone();
}

void serviceWaterAlarm() {
  if (!waterAlarm) {
    return;
  }
  unsigned long now = millis();
  if (now - lastAlarmBeep >= ALARM_INTERVAL_MS) {
    buzzer.tone(WATER_ALARM_FREQ_HZ, WATER_ALARM_BEEP_MS);
    lastAlarmBeep = now;
  }
}

// --------------------------------------------------------------- power button

void flushSerialInput() {
  while (Serial.available() > 0) {
    Serial.read();
  }
}

void setSystemPower(bool on) {
  if (systemOn == on) {
    return;
  }
  systemOn = on;
  flushSerialInput();

  if (systemOn) {
    Serial.println("EVENT:POWER_ON");
    drawProgress(1);
  } else {
    stopWaterAlarm();
    clearMatrix();
    Serial.println("EVENT:POWER_OFF");
  }
}

void handlePowerButton() {
  bool down = (digitalRead(PIN_POWER_BTN) == LOW);
  unsigned long now = millis();

  if (down && !powerWasDown) {
    powerDownTime = now;
  } else if (!down && powerWasDown && (now - powerDownTime) >= POWER_DEBOUNCE_MS) {
    setSystemPower(!systemOn);
  }
  powerWasDown = down;
}

// ----------------------------------------------------------------- modulino IO

void handleKnob() {
  int8_t direction = knob.getDirection();
  if (direction > 0) {
    Serial.println("EVENT:KNOB_RIGHT");
  } else if (direction < 0) {
    Serial.println("EVENT:KNOB_LEFT");
  }

  bool down = knob.isPressed();
  unsigned long now = millis();

  if (down && !knobWasDown) {
    knobPressTime = now;
    knobLongFired = false;
  }

  if (down && !knobLongFired && (now - knobPressTime >= KNOB_LONG_PRESS_MS)) {
    Serial.println("EVENT:LONG_PRESS_DEMO");
    knobLongFired = true;
  }

  if (!down && knobWasDown && !knobLongFired && (now - knobPressTime >= 50)) {
    Serial.println("EVENT:CLICK");
  }

  // Acknowledge a watering alert locally by pressing the knob.
  if (down && waterAlarm) {
    stopWaterAlarm();
  }

  knobWasDown = down;
}

void pushClimate() {
  unsigned long now = millis();
  if (now - lastSensorPush < CLIMATE_INTERVAL_MS) {
    return;
  }

  float temp = thermo.getTemperature();
  float hum  = thermo.getHumidity();
  if (isnan(temp) || isnan(hum)) {
    temp = 22.5;
    hum = 55.0;
  }

  Serial.print("CLIMATE:");
  Serial.print(temp, 1);
  Serial.print(",");
  Serial.println(hum, 1);
  lastSensorPush = now;
}

void handleSerialCommands() {
  if (Serial.available() <= 0) {
    return;
  }

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();

  if (cmd.startsWith("ZONE:")) {
    highlightZoneOnMatrix(cmd.substring(5).toInt());
  } else if (cmd.startsWith("PROG:")) {
    drawProgress(cmd.substring(5).toInt());
  } else if (cmd == "ALERT:WATER") {
    startWaterAlarm();
  } else if (cmd == "ALERT:CLEAR" || cmd == "ALERT:OK") {
    stopWaterAlarm();
  }
}

void setup() {
  Serial.begin(115200);
  matrix.begin();

  pinMode(PIN_POWER_BTN, INPUT_PULLUP);

  Modulino.begin();  // defaults to Wire1 on UNO Q
  if (!knob.begin()) {
    Serial.println("WARN:KNOB_MISSING");
  }
  if (!thermo.begin()) {
    Serial.println("WARN:THERMO_MISSING");
  }
  if (!buzzer.begin()) {
    Serial.println("WARN:BUZZER_MISSING");
  }

  drawProgress(1);
}

void loop() {
  // Power button is always polled so the system can be switched back on.
  handlePowerButton();

  if (systemOn) {
    handleKnob();
    serviceWaterAlarm();
    pushClimate();
    handleSerialCommands();
  }

  delay(10);  // keep the I2C bus free for the Modulino modules
}
