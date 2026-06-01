#include <PZEM004Tv30.h>
#include <DHT.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// --- PIN DEFINITIONS ---
#define DHTPIN 2
#define DHTTYPE DHT11
#define IR_PIN 5
#define RELAY_PIN 7
#define BUZZER_PIN 8

// --- INITIALIZE MODULES ---
// The V3 library handles SoftwareSerial natively, keeping the buffer cleaner
PZEM004Tv30 pzem(10, 11); 
DHT dht(DHTPIN, DHTTYPE);

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

void setup() {
  Serial.begin(9600);
  dht.begin();
  
  pinMode(IR_PIN, INPUT);
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  // Initialize OLED
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    // Print errors in JSON format so Python doesn't crash on boot
    Serial.println(F("{\"Error\": \"OLED failed\"}")); 
    for(;;); 
  }
  
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  // Energize-to-trip sequence
  digitalWrite(RELAY_PIN, HIGH); 
  digitalWrite(BUZZER_PIN, LOW);
  
  delay(2000); 
}

void loop() {
  // 1. READ PZEM SENSORS FIRST
  float v = pzem.voltage();
  float i = pzem.current();
  float p = pzem.power();
  float e = pzem.energy();
  
  // Micro-pause allows the SoftwareSerial buffer to completely clear 
  // before the DHT11 disables the hardware interrupts.
  delay(50); 
  
  // 2. READ DHT & DIGITAL SENSORS
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  int irState = digitalRead(IR_PIN);

  // 3. INDEPENDENT NaN CLEANUP (Crucial for Python JSON parser)
  if(isnan(v)) v = 0.0;
  if(isnan(i)) i = 0.0;
  if(isnan(p)) p = 0.0;
  if(isnan(e)) e = 0.0;
  if(isnan(t)) t = 0.0;
  if(isnan(h)) h = 0.0;

  // 4. HARDWARE SAFETY INTERLOCK
  int isSafe;
  String statusText;

  if (irState == HIGH || v > 250.0) { 
    digitalWrite(RELAY_PIN, LOW);   
    digitalWrite(BUZZER_PIN, HIGH); 
    isSafe = 0;                     
    statusText = "";
  } else {
    digitalWrite(RELAY_PIN, HIGH);  
    digitalWrite(BUZZER_PIN, LOW);  
    isSafe = 1;                     
    statusText = "STATUS: SAFE";      
  }

  // 5. UPDATE LOCAL OLED DISPLAY
  display.clearDisplay();
  display.setTextSize(1);
  display.setCursor(0, 0); display.print(F("Power usage Analyser"));
  display.setCursor(0, 10); display.print(statusText);
  display.drawLine(0, 18, 128, 18, SSD1306_WHITE);

  display.setCursor(0, 24); display.print(F("V: ")); display.print(v, 1); display.print(F("V  ")); 
  display.print(F(" T: ")); display.print(t, 1); display.print(F("C"));
  
  display.setCursor(0, 36); display.print(F("I: ")); display.print(i, 2); display.print(F("A  "));
  display.print(F("H: ")); display.print(h, 0); display.print(F("%"));
  
  display.setCursor(0, 48); display.print(F("P: ")); display.print(p, 1); display.print(F("W"));
  display.display();

  // 6. STREAM HIGH-SPEED JSON TO PYTHON
  Serial.print("{\"V\":"); Serial.print(v, 1);
  Serial.print(",\"I\":"); Serial.print(i, 3);
  Serial.print(",\"P\":"); Serial.print(p, 1);
  Serial.print(",\"E\":"); Serial.print(e, 4);
  Serial.print(",\"T\":"); Serial.print(t, 1);
  Serial.print(",\"H\":"); Serial.print(h, 0);
  Serial.print(",\"Safe\":"); Serial.print(isSafe);
  Serial.println("}"); 

  delay(1500);
}