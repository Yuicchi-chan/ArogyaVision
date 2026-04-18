# 🔍 BP Monitor - Debugging Checklist

If BP data still isn't showing after upload, use this step-by-step debugging guide.

---

## ✅ Pre-Flight Checks

### 1. Verify Hardware Connection
- [ ] USB cable connected from PC/Raspberry Pi to BP ESP32
- [ ] BP monitor power ON (check LED indicator)
- [ ] Leads connected to BP monitor (if separate device)

### 2. Check Arduino Code Uploaded
- [ ] Look at ESP32 LED: Does it blink? (should flash once on boot)
- [ ] Serial Monitor shows: `BP Monitor Reader Started`
- [ ] If not: **Upload again**

### 3. Verify Port Detected
```bash
# List all USB devices
ls -la /dev/tty*

# Expected output should show:
# /dev/ttyUSB0  ← BP ESP32 (this is correct)
# OR
# /dev/ttyACM0  ← Vitals ESP32
```

---

## ❌ Problem: BP Data Still "Data=00045" Format

### Step 1: Confirm Old Code is NOT Running
```bash
cat /dev/ttyUSB0 &
# Let it run for 5 seconds, then Ctrl+C

# If you see: "Data=00045" → OLD CODE STILL RUNNING
# If you see: JSON or nothing → Arduino didn't upload
```

### Step 2: Re-upload Code
**In Arduino IDE:**
1. Click **Sketch → Upload** again
2. Watch Serial Monitor output
3. Should show: `BP Monitor Reader Started`

**If upload fails:**
- [ ] Check board is set to: `ESP32 Dev Module`
- [ ] Check port is: `/dev/ttyUSB0`
- [ ] Try **Tools → Get Board Info** to verify connection
- [ ] Try lower upload speed: 115200 → 9600

### Step 3: Check ArduinoJson Library
In Arduino IDE:
- [ ] **Sketch → Include Library → Manage Libraries**
- [ ] Search: `ArduinoJson`
- [ ] Should show **INSTALLED** badge
- [ ] If not installed: Install version 6.21+ by Benoit Blanchon

---

## ❌ Problem: Serial Monitor Shows NOTHING

### Step 1: Check USB Connection
```bash
# Monitor USB events
sudo dmesg | tail -20

# You should see:
# ch341-uart converter now attached to ttyUSB0
# OR
# ftdi_sio 1-1:1.0: FTDI USB Serial Device converter detected
```

### Step 2: Check Serial Monitor Settings
- [ ] Baud rate is: **115200**
- [ ] Port shows: `/dev/ttyUSB0`
- [ ] Click **Serial Monitor** (not Plotter)

### Step 3: Check Reset Behavior
Try holding **BOOT** button on ESP32 while uploading:
1. Press and hold BOOT button
2. Click Upload in Arduino IDE
3. Release BOOT button when upload finishes

---

## ❌ Problem: BP Values Are Wrong (e.g., always 120/80)

### Step 1: Verify Sensor Input
If BP monitor is a **separate device** (not built into ESP32):
- [ ] Check physical leads are connected to the device
- [ ] Check power to BP device (LED on?)
- [ ] Try inserting arm and pressing START on BP device

### Step 2: Check BP Device Format
Run diagnostic to see raw BP output:
```bash
python3 /home/pi/Desktop/New/ArogyaVision/debug_bp_raw.py

# This will show actual bytes being transmitted
# Look for patterns like:
# "Sys[0]=00120 DIA[0]=00080" → Recognized format
# "Data=00120 Data=00080" → Old format, needs parsing fix
```

### Step 3: Check Baud Rate
Try different baud rates in Arduino code:

**Current (in code):**
```cpp
bpSerial.begin(9600, SERIAL_8N1, 16, 17);  // 9600 baud
```

**Try these if BP is sending garbage:**
- 4800 baud
- 19200 baud
- 38400 baud
- 115200 baud

Change the number in line ~24 and **Upload again**.

---

## ❌ Problem: Python App Says "No BP Data"

### Step 1: Run Connection Test
```bash
cd /home/pi/Desktop/New/ArogyaVision
python3 test_bp_connection.py

# Expected output:
# ✅ /dev/ttyUSB0 appears to be the BP monitor!
# Results for /dev/ttyUSB0:
#   Lines received: 5
#   Valid JSON lines: 2 ✓
```

### Step 2: Check JSON Format
Expected JSON in test output:
```json
{"sys": 120, "dia": 80, "pulse": 70, "status": "completed"}
```

If not JSON, look at raw data:
```bash
python3 debug_bp_raw.py | head -20

# Shows actual format being sent
```

### Step 3: Check app.py read_bp_data()
Verify this function is correct:

```python
def read_bp_data():
    if bp_ser and bp_ser.in_waiting > 0:
        try:
            line = bp_ser.readline().decode('utf-8').strip()
            if line.startswith('{'):  # JSON format
                data = json.loads(line)
                if 0 < data['sys'] < 250 and 0 < data['dia'] < 200 and 0 < data['pulse'] < 180:
                    return data
        except:
            pass
    return None
```

---

## ✅ Final Verification Steps

### 1. Test Each Component Separately

#### ✓ Test Vitals ESP32 (should already work)
```bash
python3 test_api.py
# Should show: Temperature, Heart Rate, SpO2 values
```

#### ✓ Test BP ESP32
```bash
python3 test_bp_connection.py
# Should show: Valid JSON with sys/dia/pulse values
```

### 2. Test Full App
```bash
streamlit run app.py

# Complete workflow:
# 1. Click "Start"
# 2. Wait 20 seconds for vitals (should show real values)
# 3. Click "Confirm Vitals"
# 4. See BP Measurement screen
# 5. Wait 30 seconds (should show live BP values being collected)
# 6. Click "Confirm BP"
# 7. Select symptoms
# 8. See final report with BOTH vitals and BP
```

---

## 📋 Common Issues Reference

| Problem | Cause | Solution |
|---------|-------|----------|
| "Data=00045" format | Old Arduino code on device | Re-upload from `bp_monitor_esp32.ino` |
| No data at all | Serial port wrong | Check `ls /dev/tty*` |
| Garbage in Serial Monitor | Wrong baud rate | Try 9600, 19200, 115200 |
| Upload fails | Wrong board/port | Set ESP32 Dev Module & /dev/ttyUSB0 |
| Still wrong format | ArduinoJson not installed | Install via Library Manager |
| Values always 120/80 | BP sensor not connected | Check physical connections |
| Python says "No BP" | JSON parsing error | Run `test_bp_connection.py` |

---

## 🆘 Still Not Working?

Run this complete diagnostic:
```bash
#!/bin/bash

echo "=== 1. Hardware Check ==="
ls -la /dev/tty*

echo "=== 2. Port Detection ==="
python3 test_bp_connection.py

echo "=== 3. Raw Data ==="
python3 debug_bp_raw.py

echo "=== 4. App Status ==="
grep "BP_SERIAL_PORT\|BP_PORT\|read_bp_data" app.py | head -10
```

Then share the output with troubleshooting support.
