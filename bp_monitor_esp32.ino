#include <HardwareSerial.h>
#include <ArduinoJson.h>

HardwareSerial bpSerial(2);   // UART2 on ESP32

// BP board connection:
// BP TX -> ESP32 GPIO16
// BP RX -> ESP32 GPIO17
// GND   -> ESP32 GND

String lineBuffer = "";

int SYS   = 0;
int DIA   = 0;
int PULSE = 0;

unsigned long lastDataTime = 0;
bool measurementFinished = false;

void setup() {
  Serial.begin(115200);

  // Try 9600 first. If no output, try 4800 / 19200
  bpSerial.begin(9600, SERIAL_8N1, 16, 17);

  Serial.println("\nBP Monitor Reader Started");
  Serial.println("Waiting for measurement...");
}

void loop() {

  while (bpSerial.available()) {
    char c = bpSerial.read();
    lastDataTime = millis();

    // End of one serial line
    if (c == '\n' || c == '\r') {

      if (lineBuffer.length() > 0) {
        Serial.println(lineBuffer);

        // Final result line usually contains Data=
        if (lineBuffer.indexOf("Data=") >= 0) {
          parseFinalData(lineBuffer);
          measurementFinished = true;
        }

        // Backup: also parse Sys[] and DIA[] if present
        if (lineBuffer.indexOf("Sys[0]") >= 0) {
          SYS = extractAfter(lineBuffer, "Sys[0]=");
        }

        if (lineBuffer.indexOf("DIA[0]") >= 0) {
          DIA = extractAfter(lineBuffer, "DIA[0]=");
        }

        lineBuffer = "";
      }
    } else {
      lineBuffer += c;
    }
  }

  // Measurement completed and no new data for 2 seconds
  if (measurementFinished && (millis() - lastDataTime > 2000)) {

    Serial.println("\n===== FINAL RESULT =====");
    Serial.print("SYS   : ");
    Serial.print(SYS);
    Serial.println(" mmHg");

    Serial.print("DIA   : ");
    Serial.print(DIA);
    Serial.println(" mmHg");

    Serial.print("PULSE : ");
    Serial.print(PULSE);
    Serial.println(" bpm");

    // Output JSON format for Python parsing
    sendJSONData(SYS, DIA, PULSE);

    Serial.println("========================\n");

    // reset for next measurement
    measurementFinished = false;
    SYS = 0;
    DIA = 0;
    PULSE = 0;
  }
}

// ---------------------------------------------------
// Send data in JSON format for easy Python parsing
// ---------------------------------------------------
void sendJSONData(int sys, int dia, int pulse) {
  StaticJsonDocument<200> doc;
  
  doc["sys"] = sys;
  doc["dia"] = dia;
  doc["pulse"] = pulse;
  doc["status"] = "completed";
  
  serializeJson(doc, Serial);
  Serial.println();  // newline for line-based parsing
}

// ---------------------------------------------------
// Extracts number after a keyword like Sys[0]=
// Example: "Sys[0]=00104" -> 104
// ---------------------------------------------------
int extractAfter(String s, String key) {
  int pos = s.indexOf(key);

  if (pos < 0) return 0;

  pos += key.length();

  String num = "";

  while (pos < s.length() && isDigit(s[pos])) {
    num += s[pos];
    pos++;
  }

  return num.toInt();
}

// ---------------------------------------------------
// Parse line like:
// Data=00001 Data=00088 Data=00064 Data=00105 ...
//
// According to your machine:
// values[1] = Pulse
// values[2] = DIA
// values[3] = SYS
// ---------------------------------------------------
void parseFinalData(String s) {

  int values[10];
  int count = 0;

  while (count < 10) {

    int pos = s.indexOf("Data=");

    if (pos < 0) break;

    s = s.substring(pos + 5);

    String number = "";

    for (int i = 0; i < s.length(); i++) {
      if (isDigit(s[i])) {
        number += s[i];
      } else {
        break;
      }
    }

    values[count] = number.toInt();
    count++;

    int nextSpace = s.indexOf(' ');
    if (nextSpace < 0) break;

    s = s.substring(nextSpace + 1);
  }

  // Example packet:
  // Data=00001
  // Data=00088  -> pulse
  // Data=00064  -> DIA
  // Data=00105  -> SYS

  if (count >= 4) {
    PULSE = values[1];
    DIA   = values[2];
    SYS   = values[3];
  }

  Serial.println("\nDetected Final Packet:");
  Serial.print("SYS   = ");
  Serial.println(SYS);

  Serial.print("DIA   = ");
  Serial.println(DIA);

  Serial.print("PULSE = ");
  Serial.println(PULSE);
}
