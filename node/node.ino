#include <Arduino.h>
#include <SPI.h>
#include <MFRC522.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ESP8266HTTPClient.h>
#include <ArduinoJson.h>
#include <WiFiClientSecure.h>

#include "secrets.h"

// =================== CONFIG ===================

// Pins
// RC522 (SCK=D5, MISO=D6, MOSI=D7)
#define PIN_TRIG      D1
#define PIN_ECHO      D2
#define PIN_SS        D8      // RC522 SDA/SS
#define PIN_RST       D0      // RC522 reset
#define PIN_LED_GREEN D3
#define PIN_LED_RED   3

// Ultrasonic settings
const uint16_t US_SAMPLE_PERIOD_MS       = 100;
const float    CAR_DISTANCE_THRESHOLD_CM = 25.0;
const uint8_t  STABLE_COUNT_THRESHOLD    = 5;     // debounce samples

// Timers
const uint32_t RESERVATION_TIMEOUT_MS = 120000;  // 120 s
const uint32_t AUTH_TIMEOUT_MS        = 60000;   // 60 s
const uint32_t RETRY_TIMEOUT_MS       = 5000;    // 05 s

// RFID
MFRC522 rfid(PIN_SS, PIN_RST);

// HTTPS
WiFiClientSecure espClient;

// MQTT
WiFiClient mqttClient;
PubSubClient mqtt(mqttClient);

// =================== STATE MACHINE ===================

enum NodeState : uint8_t {
  ST_FREE,
  ST_RESERVED,
  ST_WAIT_AUTH,
  ST_UNAUTHORIZED,
  ST_VIOLATION,
  ST_OCCUPIED
};

const char* stateToStr(NodeState s) {
  switch (s) {
    case ST_FREE:        return "FREE";
    case ST_RESERVED:    return "RESERVED";
    case ST_WAIT_AUTH:   return "WAIT_AUTH";
    case ST_UNAUTHORIZED:return "UNAUTHORIZED";
    case ST_VIOLATION:   return "VIOLATION";
    case ST_OCCUPIED:    return "OCCUPIED";
    default:             return "ERROR";
  }
}

NodeState curState = ST_FREE;
NodeState originState = ST_FREE;

// =================== VARIABLES ===================

uint32_t stateEnterTime       = 0;
uint32_t lastUltrasonicMs     = 0;
uint32_t lastLEDBlinkMs       = 0;

bool     occupancy            = false;     // true = car detected
bool     prevOccupancy        = false;
uint8_t  stabilityCounter     = 0;

bool     ledBlinkState        = false;
uint16_t BLINK_PERIOD         = 400;

bool     mqttReservedFlag     = false;
bool     mqttCancellationFlag = false;
String   topicReserve         = "nodes/" + String(ID_NODE);

bool     invalidCardTried     = false;
bool     validCardTried       = false;
bool     violation            = false;

MFRC522::MIFARE_Key KNOWN_KEY = {
  {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF}
};

const byte TARGET_SECTOR = 1;
const byte AUTH_BLOCK    = TARGET_SECTOR * 4;   // sector 1 -> block 4 (data block)

// =================== LEDS ===================

void ledsOff() {
  digitalWrite(PIN_LED_GREEN, LOW);
  digitalWrite(PIN_LED_RED,   LOW);
}

void updateLEDs() {
  uint32_t now = millis();

  if (now - lastLEDBlinkMs >= BLINK_PERIOD) {
    lastLEDBlinkMs = now;
    ledBlinkState = !ledBlinkState;
  }

  bool green = false;
  bool red   = false;
  bool blink = false;

  switch (curState) {
    case ST_FREE:
      green = true;
      break;

    case ST_RESERVED:
      // ORANGE 
      green = true;
      red   = true;
      break;

    case ST_WAIT_AUTH:
      blink = true;
      green = ledBlinkState;
      red   = ledBlinkState;
      break;

    case ST_UNAUTHORIZED:
    case ST_VIOLATION:
      blink = true;
      red   = ledBlinkState;
      break;

    case ST_OCCUPIED:
      red = true;
      break;
  }

  if (!blink) {
    digitalWrite(PIN_LED_GREEN, green ? HIGH : LOW);
    digitalWrite(PIN_LED_RED,   red   ? HIGH : LOW);
  } else {
    digitalWrite(PIN_LED_GREEN, green);
    digitalWrite(PIN_LED_RED,   red);
  }
}

// =================== ULTRASONIC ===================

float readUltrasonicDistance() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(3);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(11);
  digitalWrite(PIN_TRIG, LOW);

  unsigned long duration = pulseIn(PIN_ECHO, HIGH, 60000UL);

  if (duration == 0) return 9999.0f; 
  return duration * 0.0343f / 2.0f;
}

void updateUltrasonic() {
  uint32_t now = millis();
  if (now - lastUltrasonicMs < US_SAMPLE_PERIOD_MS) return;
  lastUltrasonicMs = now;

  float dist = readUltrasonicDistance();
  if (dist < 10){
    Serial.println("[SONIC] Detection error <10cm");
    return;
  } 

  bool detected;
  if (dist > 500) {
    detected = false;
  } else {
    detected = (dist < CAR_DISTANCE_THRESHOLD_CM);
  }

  if (detected == prevOccupancy) {
    if (stabilityCounter < STABLE_COUNT_THRESHOLD) {
      stabilityCounter++;
    }
  } else {
    stabilityCounter = 1;
    prevOccupancy = detected;
  }

  if (stabilityCounter >= STABLE_COUNT_THRESHOLD) {
    if (occupancy != detected) {
      occupancy = detected;
      Serial.printf("Occupancy changed: %s (%.1f cm)\n", occupancy ? "YES" : "NO", dist);
    }
  }
}

// =================== RFID ===================

bool selectCard() {
  if (!rfid.PICC_IsNewCardPresent()) return false;
  if (!rfid.PICC_ReadCardSerial())   return false;
  return true;
}

void endCardSession() {
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  delay(50);
}

String readCardUID() {
  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  return uid;
}

bool readCurrentAuthBytes(byte blockAddr, byte* currentBytes) {
  MFRC522::StatusCode status = rfid.PCD_Authenticate(
    MFRC522::PICC_CMD_MF_AUTH_KEY_A,
    blockAddr,
    &KNOWN_KEY,
    &(rfid.uid)
  );

  if (status != MFRC522::STATUS_OK) {
    Serial.printf("[RFID] Auth failed: %s\n", rfid.GetStatusCodeName(status));
    endCardSession();
    return false;
  }

  byte buffer[18];
  byte size = sizeof(buffer);

  status = rfid.MIFARE_Read(blockAddr, buffer, &size);
  if (status != MFRC522::STATUS_OK) {
    Serial.printf("[RFID] Read failed: %s\n", rfid.GetStatusCodeName(status));
    endCardSession();
    return false;
  }

  memcpy(currentBytes, buffer, 8);

  Serial.print("[RFID] Current AUTH_BYTES: ");
  for (int i = 0; i < 8; i++) Serial.printf("%02X ", currentBytes[i]);
  Serial.println();

  return true;
}

void generateNewAuthBytes(byte* newBytes) {
  for (int i = 0; i < 8; i++) newBytes[i] = (byte)random(0, 256);
}

bool replaceAuthBytes(byte blockAddr, const byte* newBytes) {
  MFRC522::StatusCode status = rfid.PCD_Authenticate(
    MFRC522::PICC_CMD_MF_AUTH_KEY_A,
    blockAddr,
    &KNOWN_KEY,
    &(rfid.uid)
  );

  if (status != MFRC522::STATUS_OK) {
    Serial.printf("[RFID] Auth failed: %s\n", rfid.GetStatusCodeName(status));
    endCardSession();
    return false;
  }

  byte buffer[18];
  byte size = sizeof(buffer);

  status = rfid.MIFARE_Read(blockAddr, buffer, &size);
  if (status != MFRC522::STATUS_OK) {
    Serial.printf("[RFID] Read failed: %s\n", rfid.GetStatusCodeName(status));
    endCardSession();
    return false;
  }

  // Prepare 16-byte block payload
  byte blockData[16];
  memcpy(blockData, buffer, 16);

  // Replace first 6 bytes only
  memcpy(blockData, newBytes, 8);

  status = rfid.MIFARE_Write(blockAddr, blockData, 16);
  if (status != MFRC522::STATUS_OK) {
    Serial.printf("[RFID] Write failed: %s\n", rfid.GetStatusCodeName(status));
    endCardSession();
    return false;
  }
  Serial.printf("[RFID] Write successful: %s\n", rfid.GetStatusCodeName(status));
  endCardSession();
  return true;
}


String bytesToHex(const byte* bytes) {
  String s;
  for (int i = 0; i < 8; i++) {
    if (bytes[i] < 0x10) s += "0";
    s += String(bytes[i], HEX);
  }
  s.toUpperCase();
  return s;
}

void checkRFID() {
  if (curState != ST_WAIT_AUTH) return;

  if (!selectCard()) return;

  String uid = readCardUID();
  if (uid.length() == 0) {
    endCardSession();
    return;
  }

  Serial.print("[RFID] Detected UID: ");
  Serial.println(uid);

  byte currentAuth[8] = {0};
  if (!readCurrentAuthBytes(AUTH_BLOCK, currentAuth)) {
    invalidCardTried = true;
    validCardTried   = false;
    endCardSession();
    return;
  }

  String authBytesHex = bytesToHex(currentAuth);

  byte newAuth[8];
  generateNewAuthBytes(newAuth);
  String newAuthBytesHex = bytesToHex(newAuth);

  if(!replaceAuthBytes(AUTH_BLOCK, newAuth)){
    invalidCardTried = true;
    endCardSession();
    return;
  }

  String payload = buildAuthPayload(uid, authBytesHex, newAuthBytesHex);
  String authResult = requestBackendAuthorization(payload);

  if (authResult == "success") {
    validCardTried   = true;
    invalidCardTried = false;
    violation        = false;
  }
  else if (authResult == "violation") {
    validCardTried   = false;
    invalidCardTried = false;
    violation        = true;
  }
  else if (authResult == "invalid") {
    validCardTried   = false;
    invalidCardTried = true;
    violation        = false;
  }
  else {
    validCardTried   = false;
    invalidCardTried = false;
    violation        = false;
  }

  endCardSession();
}

// =================== HTTP ===================

void sendNodeStatusUpdate(const char* newStatus) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[HTTP] WiFi disconnected - ERROR");
    return; 
  }
  String url = String(API_BASE_URL) + "/nodes/" + String(ID_NODE);

  StaticJsonDocument<256> doc;
  doc["data_to_update"]["status"] = newStatus;
  doc["source"] = "node";
  doc["token"] = NODE_SECRET_TOKEN;

  String payload;
  serializeJson(doc, payload);

  HTTPClient http;
  http.begin(espClient, url);
  http.addHeader("Content-Type", "application/json");

  int code = http.PATCH(payload);

  if (code > 0) {
    Serial.printf("[HTTP] PATCH %s: %d \n", newStatus, code);
  } else {
    Serial.printf("[HTTP] PATCH failed %s\n", http.errorToString(code).c_str());
  }
  http.end();
}

String buildAuthPayload(const String& uid, const String& authBytes, const String& newAuthBytes) {
  StaticJsonDocument<512> doc;

  JsonObject user_data = doc.createNestedObject("user_data");
  user_data["UID"]           = uid;
  user_data["AUTH_BYTES"]    = authBytes;
  user_data["NEW_AUTH_BYTES"] = newAuthBytes;

  doc["token"] = NODE_SECRET_TOKEN;

  String payload;
  serializeJson(doc, payload);

  return payload;
}

String requestBackendAuthorization(const String& payload) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[HTTP] WiFi disconnected");
    return "error"; 
  }

  String url = String(API_BASE_URL) + "/nodes/" + String(ID_NODE);

  HTTPClient http;
  http.begin(espClient, url);
  http.addHeader("Content-Type", "application/json");

  Serial.println("[AUTH] POST: " + url);
  Serial.println("Payload: " + payload);

  int code = http.POST(payload);

  String backendStatus = "error";   // default

  Serial.printf("[AUTH] Code response: %d\n", code);
  if (code > 0) {
    String response = http.getString();
    Serial.printf("[AUTH] Code %d : %s\n", code, response.c_str());

    StaticJsonDocument<512> resp;
    DeserializationError err = deserializeJson(resp, response);

    if (!err) {
      backendStatus = resp["status"] | "unknown";
    }
  } else {
    Serial.printf("[AUTH HTTP failed] %s and %d\n", http.errorToString(code).c_str(), code);
  }

  http.end();

  Serial.printf("[AUTH] Backend status: %s\n", backendStatus.c_str());
  return backendStatus; 
}

// =================== MQTT ===================

bool mqttConnect() {
  if (mqtt.connected()) return true;

  String nodeId = String(ID_NODE);

  Serial.print("[MQTT] Connecting as ");
  Serial.println(nodeId);

  if (mqtt.connect(nodeId.c_str())) { //   if (mqtt.connect(nodeId.c_str(), MQTT_USERNAME, MQTT_PASSWORD)) {
    Serial.println("[MQTT] Connected");
    mqtt.subscribe(topicReserve.c_str());
    return true;
  } else {
    Serial.print("[MQTT] Failed: ");
    Serial.println(mqtt.state());
    return false;
  }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("] ");

  String message = "";
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.println(message);

  if (message == "reserved") {
    if (curState == ST_FREE || curState == ST_WAIT_AUTH || curState == ST_UNAUTHORIZED) {
      mqttReservedFlag = true;
      Serial.println("[MQTT] RESERVED");
    }
  }
  else if (message == "free") {
    if (curState == ST_RESERVED || originState == ST_RESERVED){
      originState = ST_RESERVED;
      mqttCancellationFlag = true;
      Serial.println("[MQTT] CANCELLATION");
    }
  }
}

// =================== WIFI  ===================

void connectWiFi() {
  Serial.print("[WIFI] Connecting ");

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.print("[WIFI] Connected: ");
  Serial.println(WiFi.localIP());
}

// =================== STATE MACHINE LOGIC ===================

void runStateMachine() {
  uint32_t now = millis();
  uint32_t timeInState = now - stateEnterTime;

  switch (curState) {

    case ST_FREE:
      if (occupancy) {
        curState = ST_WAIT_AUTH;
        stateEnterTime = now;
        Serial.println("\n====== [STATE] Car detected (FREE => WAIT_AUTH) ======");
      } 
      else if (mqttReservedFlag) {
        mqttReservedFlag = false;
        curState = ST_RESERVED;
        originState = ST_RESERVED;
        stateEnterTime = now;
        Serial.println("\n====== [STATE] Reserved (FREE => RESERVED) ======");
      }
      break;

    case ST_RESERVED:
      if (occupancy) {
        curState = ST_WAIT_AUTH;
        stateEnterTime = now;
        Serial.println("\n====== [STATE] Car detected (RESERVED => WAIT_AUTH) ======");
      }
      else if (timeInState > RESERVATION_TIMEOUT_MS) {
        curState = ST_FREE;
        originState = ST_FREE;
        stateEnterTime = now;
        Serial.println("\n====== [STATE] Timeout (RESERVED => FREE) ======");
        sendNodeStatusUpdate("free");

      }
      else if (mqttCancellationFlag) {
        curState = ST_FREE;
        originState = ST_FREE;
        mqttCancellationFlag = false;
        stateEnterTime = now;
        Serial.println("\n====== [STATE] Cancelled (RESERVED => FREE) ======");
      }
      break;

    case ST_WAIT_AUTH:
      if ((timeInState > AUTH_TIMEOUT_MS) || violation) {
        curState = ST_VIOLATION;
        stateEnterTime = now;
        Serial.println("\n====== [STATE] Timeout (WAIT_AUTH => VIOLATION) ======");
        sendNodeStatusUpdate("violation");
      }
      else if (invalidCardTried) {
        curState = ST_UNAUTHORIZED;
        stateEnterTime = now;
        Serial.println("\n====== [STATE] Invalid ID (WAIT_AUTH => UNAUTHORIZED) ======");
      }
      else if (validCardTried) {
        curState = ST_OCCUPIED;
        stateEnterTime = now;
        Serial.println("\n====== [STATE] Valid ID (WAIT_AUTH => OCCUPIED) ======");
      }
      else if (!occupancy) {
        curState = originState;
        stateEnterTime = now;
        Serial.println("\n====== [STATE] Car left (WAIT_AUTH => FREE/RESERVED) ======");
      }
      break;

    case ST_UNAUTHORIZED:
      if (timeInState > RETRY_TIMEOUT_MS) {
        curState = ST_WAIT_AUTH;
        stateEnterTime = now;
        Serial.println("\n\t[STATE] Retry (UNAUTHORIZED => WAIT_AUTH)");
        invalidCardTried = false;
        //sendNodeStatusUpdate("waiting_for_authentication");
      }
      break;

    case ST_VIOLATION:
      if (!occupancy) {
        curState = originState;
        stateEnterTime = now;
        violation = false;
        Serial.println("\n\t[STATE] Car left (ST_VIOLATION => FREE/RESERVED)");
        sendNodeStatusUpdate(originState == ST_RESERVED ? "reserved" : "free");
      }
      break;

    case ST_OCCUPIED:
      if (!occupancy) {
        curState = ST_FREE;
        originState = ST_FREE;
        stateEnterTime = now;
        Serial.println("\n\t[STATE] Car left (ST_OCCUPIED => ST_FREE)");
        validCardTried = false;
        sendNodeStatusUpdate("free");
      }
      break;
  }
}

// =================== SETUP ===================

void setup() {
  Serial.begin(9600);
  delay(5000);

  Serial.println("\n\n========== Begin SETUP ==========\n\n");

  pinMode(PIN_TRIG,      OUTPUT);
  pinMode(PIN_ECHO,      INPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_RED,   OUTPUT);

  digitalWrite(PIN_TRIG, LOW);
  ledsOff();

  SPI.setFrequency(1000000); // max gain to allow writing (ensure stability)
  SPI.begin();
  rfid.PCD_Init();
  rfid.PCD_SetAntennaGain(rfid.RxGain_max);  // max gain to allow writing (ensure stability)
  delay(200);

  connectWiFi();
  espClient.setFingerprint(TLS_FINGERPRINT);
  
  mqtt.setServer(MQTT_SERVER, MQTT_PORT);
  mqtt.setCallback(mqttCallback);
  mqttConnect();

  curState = ST_FREE;
  stateEnterTime = millis();
  Serial.println("\n\n========== Done SETUP ==========\n\n");
}

// =================== LOOP ===================

void loop() {
  //uint32_t now = millis();

  if (!mqtt.connected()) {
    mqttConnect();
  }
  mqtt.loop();

  updateUltrasonic();
  checkRFID();
  runStateMachine();
  updateLEDs();

  delay(100);

  //static uint32_t lastPrint = 0;
  //if (now - lastPrint >= 2000) {
  //  lastPrint = now;
  //  Serial.printf("[%-12s] car=%d\n", stateToStr(curState), occupancy);
  //}
}
