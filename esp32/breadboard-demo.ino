#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

#define FSR_PIN 4
#define FSR_LED 21
#define SCIENTIST_BUTTON 1
#define ENGINEER_BUTTON 2
#define ENTREPENUER_BUTTON 3
#define SCIENTIST_LED 20
#define ENGINEER_LED 19
#define ENTREPENUER_LED 18
#define ERROR_LED 22

#define SERVICE_UUID "12345678-1234-1234-1234-123456789abc"
#define CHARACTERISTIC_UUID "abcd1234-ab12-ab12-ab12-abcdef123456"

BLECharacteristic *pCharacteristic;
bool deviceConnected = false;
bool activated = false;

class MyServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer* pServer) { deviceConnected = true; }
  void onDisconnect(BLEServer* pServer) { deviceConnected = false; }
};

void blinkAndSend(int ledPin, String category) {
  // blink LED 3 times to indicate sending
  for (int i = 0; i < 10; i++) {
    digitalWrite(ledPin, HIGH);
    delay(500);
    digitalWrite(ledPin, LOW);
    delay(500);
  }
  // send BLE JSON payload
  if (deviceConnected) {
    String payload = "{\"category\": \"" + category + "\"}";
    pCharacteristic->setValue(payload.c_str());
    pCharacteristic->notify();

    // delay here while we wait for the bluetooth notification
    delay(3000);

    activated = false;
    digitalWrite(FSR_LED, LOW);
  } else {
    for (int i = 0; i < 20; i++) {
      digitalWrite(ERROR_LED, HIGH);
      delay(100);

      digitalWrite(ERROR_LED, LOW);
      delay(100);
    }
  }
}

void startup() {
  for (int i = 0; i < 3; i++) {
    digitalWrite(SCIENTIST_LED, HIGH);
    digitalWrite(ENGINEER_LED, HIGH);
    digitalWrite(ENTREPENUER_LED, HIGH);
    delay(500);
    
    digitalWrite(ENGINEER_LED, LOW);
    digitalWrite(ENTREPENUER_LED, LOW);
    delay(500);
    
    digitalWrite(SCIENTIST_LED, LOW);
    digitalWrite(ENGINEER_LED, HIGH);
    delay(500);
    
    digitalWrite(ENGINEER_LED, LOW);
    digitalWrite(ENTREPENUER_LED, HIGH);
    delay(500);
    
    digitalWrite(SCIENTIST_LED, HIGH);
    digitalWrite(ENGINEER_LED, HIGH);
    digitalWrite(ENTREPENUER_LED, HIGH);
    delay(500);
    
    digitalWrite(SCIENTIST_LED, LOW);
    digitalWrite(ENGINEER_LED, LOW);
    digitalWrite(ENTREPENUER_LED, LOW);
    delay(500);
  }
}

void setup() {
  pinMode(SCIENTIST_LED, OUTPUT);
  pinMode(ENGINEER_LED, OUTPUT);
  pinMode(ENTREPENUER_LED, OUTPUT);
  pinMode(FSR_LED, OUTPUT);
  pinMode(ERROR_LED, OUTPUT);
  pinMode(SCIENTIST_BUTTON, INPUT_PULLUP);
  pinMode(ENGINEER_BUTTON, INPUT_PULLUP);
  pinMode(ENTREPENUER_BUTTON, INPUT_PULLUP);

  // BLE init
  BLEDevice::init("Ethan Z ESP32-C6 Selector");
  BLEServer *pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());
  BLEService *pService = pServer->createService(SERVICE_UUID);
  pCharacteristic = pService->createCharacteristic(
    CHARACTERISTIC_UUID,
    BLECharacteristic::PROPERTY_NOTIFY
  );
  pCharacteristic->addDescriptor(new BLE2902());
  pService->start();
  BLEDevice::getAdvertising()->start();
}

void loop() {
  if (!activated) {
    // waiting for FSR activation
    int fsr = analogRead(FSR_PIN);
    if (fsr > 2000) {
      digitalWrite(FSR_LED, HIGH);
      delay(2000);
      startup();
      activated = true;
    }
      
    return; // don't do anything else until activated
  }

  // system is active — listen for button presses
  if (!digitalRead(SCIENTIST_BUTTON)) {
    blinkAndSend(SCIENTIST_LED, "scientist");
    delay(500); // debounce
  }
  if (!digitalRead(ENGINEER_BUTTON)) {
    blinkAndSend(ENGINEER_LED, "engineer");
    delay(500);
  }
  if (!digitalRead(ENTREPENUER_BUTTON)) {
    blinkAndSend(ENTREPENUER_LED, "entrepreneur");
    delay(500);
  }

  delay(10);
}
