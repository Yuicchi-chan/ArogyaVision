# Setting Up the Raspberry Pi & ESP32 for Vitals Sensors

This guide walks you through uploading the code to your ESP32, preparing your Raspberry Pi, and finally reading the sensor data on the Raspberry Pi.

---

## Step 1: Upload the Code to the ESP32 (from your PC)

It is usually easiest to upload the code to your ESP32 from your main computer (Windows/Mac) rather than from the Raspberry Pi itself.

1. **Install the Arduino IDE**: If you haven't already, download and install the [Arduino IDE](https://www.arduino.cc/en/software).
2. **Install the ESP32 Board Manager**:
   - Go to **File > Preferences**.
   - In "Additional Boards Manager URLs", add: `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
   - Go to **Tools > Board > Boards Manager**, search for `esp32`, and install it.
3. **Install Required Libraries**:
   - Go to **Sketch > Include Library > Manage Libraries**.
   - Search for and install **Adafruit MLX90614 Library**.
   - Search for and install **SparkFun MAX3010x Pulse and Proximity Sensor Library**.
4. **Upload the Code**:
   - Open the `esp32_vitals_sensors.ino` file I created for you.
   - Plug your ESP32 into your PC via USB.
   - Go to **Tools > Board** and select your ESP32 model (e.g., "DOIT ESP32 DEVKIT V1").
   - Go to **Tools > Port** and select the COM port of your ESP32.
   - Click the **Upload** arrow button (top left). Wait for it to say "Done uploading".

---

## Step 2: Set Up the Raspberry Pi

Now we need to prepare the Raspberry Pi to read data via Python.

### 1. Connect the Hardware
- Take the ESP32 (which is now programmed) and plug it directly into one of the **USB ports on your Raspberry Pi** using a data cable.

### 2. Update the Raspberry Pi and Install Python Dependencies
Open a terminal on your Raspberry Pi and run the following commands:

```bash
# Update the system packages
sudo apt update
sudo apt upgrade -y

# Install Python 3 package manager (if not already installed)
sudo apt install python3-pip -y

# Install PySerial (the library that allows Python to talk to USB devices)
pip3 install pyserial --break-system-packages
```
*(Note: on newer Raspberry Pi OS versions, you might need to use `sudo apt install python3-serial` instead if `pip` blocks global installs).*

### 3. Find the ESP32's USB Port Name
With the ESP32 plugged into the Raspberry Pi, run this command in the terminal:
```bash
ls /dev/ttyUSB*
```
- It will usually print out `/dev/ttyUSB0` or `/dev/ttyUSB1`. Make note of this, as you'll need it for the Python script.
*(If you see `/dev/ttyACM0` instead, use that).*

---

## Step 3: Run the Python Code on the Raspberry Pi

1. On your Raspberry Pi, create a new python file, for example, `read_vitals.py`:
   ```bash
   nano read_vitals.py
   ```

2. Paste the following Python code into the file (Right-click to paste in the terminal):

```python
import serial
import json
import time

# IMPORTANT: Update '/dev/ttyUSB0' if your port is different (e.g. /dev/ttyACM0)
SERIAL_PORT = '/dev/ttyUSB0'
BAUD_RATE = 115200

def main():
    print(f"Attempting to connect to ESP32 on {SERIAL_PORT}...")
    
    try:
        # Open the serial connection
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2) # Wait for connection to establish
        print("Connected successfully! Waiting for data...\n")
        
        while True:
            # Read a line of data from the ESP32
            line = ser.readline().decode('utf-8').strip()
            
            if line:
                try:
                    # The ESP32 sends data as a JSON string, so we parse it into a Python dictionary
                    data = json.loads(line)
                    
                    # Extract and print the values
                    temp = data.get('temp_obj_c', 0)
                    bpm = data.get('bpm', 0)
                    gsr = data.get('gsr', 0)
                    
                    print(f"Temperature: {temp} °C")
                    print(f"Heart Rate:  {bpm} BPM")
                    print(f"GSR (Sweat): {gsr}")
                    print("-" * 25)
                    
                except json.JSONDecodeError:
                    # If the ESP32 sends a non-JSON message (like boot info), just print it normally
                    print(f"Debug Message: {line}")
                    
    except serial.SerialException as e:
        print(f"Failed to connect: {e}")
        print("Make sure the ESP32 is plugged in and the port name is correct.")
    except KeyboardInterrupt:
        print("\nExiting program.")

if __name__ == '__main__':
    main()
```

3. Save the file in `nano` by pressing `Ctrl + X`, then `Y`, then `Enter`.
4. Run the script!
   ```bash
   python3 read_vitals.py
   ```

> [!TIP]
> If you get a "Permission denied" error when trying to run the Python script, it means your user isn't allowed to access the USB dialout ports. Fix this by running:
> `sudo usermod -a -G dialout $USER`
> Then **reboot** the Raspberry Pi and try again.
