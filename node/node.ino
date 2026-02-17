#include <Arduino.h>
#include <SPI.h>
#include <MFRC522.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ESP8266HTTPClient.h>
#include <ArduinoJson.h>

// =================== CONFIG ===================

#define ID_NODE 0
const char* NODE_SECRET_TOKEN = "MySuperSecretToken";

// WiFi
#define WIFI_SSID     "Iphone Flo"
#define WIFI_PASSWORD "IoT_Project"

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
const uint32_t RESERVATION_TIMEOUT_MS = 60000;   // 60 s
const uint32_t AUTH_TIMEOUT_MS        = 15000;   // 15 s
const uint32_t RETRY_TIMEOUT_MS       = 5000;    // 05 s

// RFID
MFRC522 rfid(PIN_SS, PIN_RST);

// MQTT
const char*    MQTT_SERVER = "broker.mqttdashboard.com";
const uint16_t MQTT_PORT   = 1883;

WiFiClient   espClient;
PubSubClient mqtt(espClient);

// Backend API
const char* API_BASE_URL = "http://172.20.10.2:5000/api";

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

uint32_t stateEnterTime     = 0;
uint32_t lastUltrasonicMs   = 0;
uint32_t lastLEDBlinkMs     = 0;

bool     occupancy          = false;     // true = car detected
bool     prevOccupancy      = false;
uint8_t  stabilityCounter   = 0;

bool     ledBlinkState      = false;
uint16_t BLINK_PERIOD       = 400;

bool     mqttReservedFlag   = false;
String   topicReserve       = "parking/node/" + String(ID_NODE) + "/reserve";

bool     invalidCardTried   = false;
bool     validCardTried     = false;
bool     violation          = false;

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
  if (dist < 0) return;

  bool detected;
  if (dist < 0 || dist > 500.0f) {          // invalid or too far
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
  rfid.PCD_StopCrypto1();
  rfid.PICC_HaltA();
}

String readCardUID() {
  if (!rfid.PICC_IsNewCardPresent()) {
    return "";
  }
  if (!rfid.PICC_ReadCardSerial()) {
    return "";
  }

  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();

  endCardSession();
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
    Serial.printf("[RFID] Auth failed block %d: %s\n", blockAddr, rfid.GetStatusCodeName(status));
    return false;
  }

  byte buffer[18];
  byte size = sizeof(buffer);

  status = rfid.MIFARE_Read(blockAddr, buffer, &size);
  if (status != MFRC522::STATUS_OK) {
    Serial.printf("[RFID] Read failed block %d: %s\n", blockAddr, rfid.GetStatusCodeName(status));
    return false;
  }

  memcpy(currentBytes, buffer, 6);

  Serial.print("[RFID] Current AUTH_BYTES read: ");
  for (int i = 0; i < 6; i++) Serial.printf("%02X ", currentBytes[i]);
  Serial.println();

  return true;
}

void generateNewAuthBytes(byte* newBytes) {
  for (int i = 0; i < 6; i++) newBytes[i] = (byte)random(0, 256);
}

bool replaceAuthBytes(byte blockAddr, const byte* newBytes) {
  MFRC522::StatusCode status = rfid.PCD_Authenticate(
    MFRC522::PICC_CMD_MF_AUTH_KEY_A,
    blockAddr,
    &KNOWN_KEY,
    &(rfid.uid)
  );

  if (status != MFRC522::STATUS_OK) {
    Serial.printf("[RFID] Auth failed block %d: %s\n", blockAddr, rfid.GetStatusCodeName(status));
    return false;
  }

  byte buffer[18];
  byte size = sizeof(buffer);

  status = rfid.MIFARE_Read(blockAddr, buffer, &size);
  if (status != MFRC522::STATUS_OK) {
    Serial.printf("[RFID] Read failed block %d: %s\n", blockAddr, rfid.GetStatusCodeName(status));
    return false;
  }

  // Prepare 16-byte block payload
  byte blockData[16];
  memcpy(blockData, buffer, 16);

  // Replace first 6 bytes only
  memcpy(blockData, newBytes, 6);

  status = rfid.MIFARE_Write(blockAddr, blockData, 16);
  if (status != MFRC522::STATUS_OK) {
    Serial.printf("[RFID] Write failed block %d: %s\n", blockAddr, rfid.GetStatusCodeName(status));
    return false;
  }

  Serial.println("[RFID] AUTH_BYTES replaced successfully (data block)");
  return true;
}

String readCardUID_NoHalt() {
  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  return uid;
}

String bytesToHex(const byte* bytes) {
  String s;
  for (int i = 0; i < 6; i++) {
    if (bytes[i] < 0x10) s += "0";
    s += String(bytes[i], HEX);
  }
  s.toUpperCase();
  return s;
}

void checkRFID() {
  if (curState != ST_WAIT_AUTH) return;

  if (!selectCard()) return;

  String uid = readCardUID_NoHalt();
  if (uid.length() == 0) {
    endCardSession();
    return;
  }

  Serial.print("[RFID] Detected UID: ");
  Serial.println(uid);

  byte currentAuth[6] = {0};
  if (!readCurrentAuthBytes(AUTH_BLOCK, currentAuth)) {
    invalidCardTried = true;
    validCardTried   = false;
    endCardSession();
    return;
  }

  String authBytesHex = bytesToHex(currentAuth);

  byte newAuth[6];
  generateNewAuthBytes(newAuth);
  String newAuthBytesHex = bytesToHex(newAuth);

  String payload = buildAuthPayload(uid, authBytesHex, newAuthBytesHex);
  String authResult = requestBackendAuthorization(payload);

  if (authResult == "success") {
    if (replaceAuthBytes(AUTH_BLOCK, newAuth)) {
      Serial.println("[ANTI-CLONE] Successfully replaced AUTH_BYTES on card");
    } else {
      Serial.println("[ANTI-CLONE] Failed to write new bytes");
    }

    validCardTried   = true;
    invalidCardTried = false;
    sendNodeStatusUpdate("occupied");
    curState = ST_OCCUPIED;
    stateEnterTime = millis();
  }
  else if (authResult == "violation") {
    invalidCardTried = true;
    curState = ST_VIOLATION;
    stateEnterTime = millis();
    sendNodeStatusUpdate("violation");
  }
  else {
    invalidCardTried = true;
    curState = ST_UNAUTHORIZED;
    stateEnterTime = millis();
    Serial.printf("[AUTH] Rejected: %s\n", authResult.c_str());
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
    Serial.printf("[PATCH %s] Code %d OK\n", newStatus, code);
  } else {
    Serial.printf("[PATCH failed] %s\n", http.errorToString(code).c_str());
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
    Serial.println("[HTTP] WiFi disconnected - ERROR");
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

  if (code > 0) {
    String response = http.getString();
    Serial.printf("[AUTH] Code %d → %s\n", code, response.c_str());

    StaticJsonDocument<512> resp;
    DeserializationError err = deserializeJson(resp, response);

    if (!err) {
      backendStatus = resp["status"] | "unknown";
    }
  } else {
    Serial.printf("[AUTH HTTP failed] %s\n", http.errorToString(code).c_str());
  }

  http.end();

  Serial.printf("[AUTH] Backend status: %s\n", backendStatus.c_str());
  return backendStatus; 
}

// =================== MQTT ===================

bool mqttConnect() {
  if (mqtt.connected()) return true;

  String nodeId = "Parking-Node" + String(ID_NODE);

  Serial.print("[MQTT] Connecting as ");
  Serial.println(nodeId);

  if (mqtt.connect(nodeId.c_str())) {
    Serial.println("[MQTT] Connected");
    mqtt.subscribe(topicReserve.c_str());
    return true;
  } else {
    Serial.print("[MQTT] Failed, ");
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
    if (curState == ST_FREE || curState == ST_UNAUTHORIZED) {
      mqttReservedFlag = true;
      stateEnterTime = millis();
      Serial.println("[MQTT] RESERVED");
    }
  }
  else if (message == "free") {
    if (curState == ST_RESERVED) {
      mqttReservedFlag = false;
      stateEnterTime = millis();
      Serial.println("[MQTT] FREE");
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
        Serial.println("[STATE] Car detected (FREE => WAIT_AUTH)");
        sendNodeStatusUpdate("waiting_for_authentication");
      } 
      else if (mqttReservedFlag) {
        curState = ST_RESERVED;
        originState = ST_RESERVED;
        stateEnterTime = now;
        Serial.println("[STATE] Reserved (FREE => RESERVED)");
        sendNodeStatusUpdate("reserved");
      }
      break;

    case ST_RESERVED:
      if (occupancy) {
        curState = ST_WAIT_AUTH;
        stateEnterTime = now;
        Serial.println("[STATE] Car detected (RESERVED => WAIT_AUTH)");
        sendNodeStatusUpdate("waiting_for_authentication");
      }
      else if (timeInState > RESERVATION_TIMEOUT_MS) {
        curState = ST_FREE;
        originState = ST_FREE;
        stateEnterTime = now;
        Serial.println("[STATE] Timeout (RESERVED => FREE)");
        sendNodeStatusUpdate("free");

      }
      else if (!mqttReservedFlag) {
        curState = ST_FREE;
        originState = ST_FREE;
        stateEnterTime = now;
        Serial.println("[STATE] Cancelled (RESERVED => FREE)");
        sendNodeStatusUpdate("free");
      }
      break;

    case ST_WAIT_AUTH:
      if ((timeInState > AUTH_TIMEOUT_MS) || violation) {
        curState = ST_VIOLATION;
        stateEnterTime = now;
        Serial.println("[STATE] Timeout (WAIT_AUTH => VIOLATION)");
        sendNodeStatusUpdate("violation");
      }
      else if (invalidCardTried) {
        curState = ST_UNAUTHORIZED;
        stateEnterTime = now;
        Serial.println("[STATE] Invalid ID (WAIT_AUTH => UNAUTHORIZED)");
        sendNodeStatusUpdate("unauthorized");
      }
      else if (validCardTried) {
        curState = ST_OCCUPIED;
        stateEnterTime = now;
        Serial.println("[STATE] Valid ID (WAIT_AUTH => OCCUPIED)");
        sendNodeStatusUpdate("occupied");
      }
      else if (!occupancy) {
        curState = originState;
        stateEnterTime = now;
        Serial.println("[STATE] Car left (WAIT_AUTH => FREE/RESERVED)");
        sendNodeStatusUpdate(originState == ST_RESERVED ? "reserved" : "free");
      }
      break;

    case ST_UNAUTHORIZED:
      if (timeInState > RETRY_TIMEOUT_MS) {
        curState = ST_WAIT_AUTH;
        stateEnterTime = now;
        Serial.println("[STATE] Retry (UNAUTHORIZED => WAIT_AUTH)");
        invalidCardTried = false;
        sendNodeStatusUpdate("waiting_for_authentication");
      }
      break;

    case ST_VIOLATION:
      if (!occupancy) {
        curState = originState;
        stateEnterTime = now;
        violation = false;
        Serial.println("[STATE] Car left (ST_VIOLATION => FREE/RESERVED)");
        sendNodeStatusUpdate(originState == ST_RESERVED ? "reserved" : "free");
      }
      break;

    case ST_OCCUPIED:
      if (!occupancy) {
        curState = ST_FREE;
        originState = ST_FREE;
        stateEnterTime = now;
        Serial.println("[STATE] Car left (ST_OCCUPIED => ST_FREE)");
        validCardTried = false;
        sendNodeStatusUpdate("free");
      }
      break;
  }
}

// =================== SETUP ===================

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\nStarting Setup");

  pinMode(PIN_TRIG,      OUTPUT);
  pinMode(PIN_ECHO,      INPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_RED,   OUTPUT);

  digitalWrite(PIN_TRIG, LOW);
  ledsOff();

  SPI.setFrequency(1000000);
  SPI.begin();
  rfid.PCD_Init();
  rfid.PCD_SetAntennaGain(rfid.RxGain_max);  // max gain to debug
  delay(200);

  connectWiFi();

  mqtt.setServer(MQTT_SERVER, MQTT_PORT);
  mqtt.setCallback(mqttCallback);

  curState = ST_FREE;
  stateEnterTime = millis();
}

// =================== LOOP ===================

void loop() {
  uint32_t now = millis();

  if (!mqtt.connected()) {
    mqttConnect();
  }
  mqtt.loop();

  updateUltrasonic();
  checkRFID();
  runStateMachine();
  updateLEDs();

  static uint32_t lastPrint = 0;
  if (now - lastPrint >= 2000) {
    lastPrint = now;
    Serial.printf("[%-12s] car=%d  time=%lus\n",
                  stateToStr(curState), occupancy, now / 1000UL);
  }
}