#include <Wire.h>
#include <Adafruit_MLX90614.h>
#include "MAX30105.h" // Works for MAX30102 as well
#include "heartRate.h"

// Initialize sensors
Adafruit_MLX90614 mlx = Adafruit_MLX90614();
MAX30105 particleSensor;

// GSR pin definition
const int GSR_PIN = 34; // ADC pin for GSR sensor

// MAX30102 Heart Rate variables
const byte RATE_SIZE = 4; // Increase this for more averaging. 4 is good.
byte rates[RATE_SIZE]; // Array of heart rates
byte rateSpot = 0;
long lastBeat = 0; // Time at which the last beat occurred
float beatsPerMinute;
int beatAvg = 0;

// Timer for non-blocking serial output
unsigned long lastPrintTime = 0;

void setup() {
  // Start Serial communication for Raspberry Pi to read
  Serial.begin(115200);
  
  // Initialize I2C on custom pins (SDA = 21, SCL = 22)
  Wire.begin(21, 22);

  // -------------------------------------
  // Initialize MLX90614 (Temperature)
  // -------------------------------------
  if (!mlx.begin()) {
    Serial.println("{\"error\": \"MLX90614 not found. Check wiring.\"}");
  }

  // -------------------------------------
  // Initialize MAX30102 (Heart Rate / SpO2)
  // -------------------------------------
  // Use default I2C port, 400kHz speed
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) { 
    Serial.println("{\"error\": \"MAX30102 not found. Check wiring.\"}");
  } else {
    particleSensor.setup(); // Configure sensor with default settings
    particleSensor.setPulseAmplitudeRed(0x0A); // Turn Red LED to low to indicate sensor is running
    particleSensor.setPulseAmplitudeGreen(0); // Turn off Green LED
  }
}

void loop() {
  // -------------------------------------
  // CONTINUOUS: Read MAX30102 (Heart Rate)
  // We read this continuously without delay to accurately catch beats
  // -------------------------------------
  long irValue = particleSensor.getIR();
  
  if (checkForBeat(irValue) == true) {
    // We sensed a beat!
    long delta = millis() - lastBeat;
    lastBeat = millis();

    beatsPerMinute = 60 / (delta / 1000.0);

    if (beatsPerMinute < 255 && beatsPerMinute > 20) {
      rates[rateSpot++] = (byte)beatsPerMinute; // Store this reading in the array
      rateSpot %= RATE_SIZE; // Wrap variable

      // Take average of readings
      beatAvg = 0;
      for (byte x = 0 ; x < RATE_SIZE ; x++) {
        beatAvg += rates[x];
      }
      beatAvg /= RATE_SIZE;
    }
  }

  // -------------------------------------
  // PERIODIC: Read other sensors and print JSON
  // Print every 1000 milliseconds (1 second)
  // -------------------------------------
  if (millis() - lastPrintTime > 1000) {
    lastPrintTime = millis();
    
    // Read GSR Sensor (Analog)
    int gsrValue = analogRead(GSR_PIN);

    // Read MLX90614 (Temperature)
    float tempObj = mlx.readObjectTempC();
    float tempAmb = mlx.readAmbientTempC();
    
    // Output everything as a JSON string for easy parsing on Raspberry Pi
    Serial.print("{\"temp_obj_c\": ");
    Serial.print(tempObj);
    Serial.print(", \"temp_amb_c\": ");
    Serial.print(tempAmb);
    Serial.print(", \"gsr\": ");
    Serial.print(gsrValue);
    Serial.print(", \"bpm\": ");
    Serial.print(beatAvg);
    Serial.println("}");
  }
}
