# ⚙️ BP ESP32 UPLOAD - QUICK START (WITH PICTURES)

This guide shows **exactly** how to upload the BP code to your second ESP32.

---

## Option A: Using Arduino IDE (EASIEST)

### 1. Download Arduino IDE
Visit: https://www.arduino.cc/en/software
- Windows: Download .exe
- Mac: Download .dmg  
- Linux (Raspberry Pi): `sudo apt install arduino`

### 2. Install ESP32 Board Support
1. Open **Arduino IDE**
2. Go to: **File → Preferences** (or **Arduino → Settings** on Mac)
3. Paste into "Additional Boards Manager URLs":
   ```
   https://dl.espressif.com/dl/package_esp32_index.json
   ```
4. Click **OK**
5. Go to: **Tools → Board → Boards Manager**
6. Search: `esp32`
7. Install **"esp32"** by Espressif Systems

### 3. Install ArduinoJson Library  
1. Go to: **Sketch → Include Library → Manage Libraries**
2. Search: `ArduinoJson`
3. Install **"ArduinoJson"** by Benoit Blanchon (latest version)

### 4. Open the Code
- **File → Open**
- Navigate to: `/home/pi/Desktop/New/ArogyaVision/bp_monitor_esp32.ino`
- Click **Open**

### 5. Configure Board Settings
In Arduino IDE, set:
| Setting | Value |
|---------|-------|
| Board | ESP32 Dev Module |
| Port | /dev/ttyUSB0 |
| Upload Speed | 115200 |
| Programmer | AVR ISP |
| Partition Scheme | Default 4MB with spiffs |

**How to set:**
1. **Tools → Board** → Select "ESP32 Dev Module"
2. **Tools → Port** → Select "/dev/ttyUSB0"
3. **Tools → Upload Speed** → Select "115200"

### 6. Upload Code
1. Click the **Upload Button** (➡️ arrow icon, top left)
2. Watch the progress bar
3. When done, you should see:
   ```
   Leaving... Hard resetting via RTS pin...
   ```

---

## Option B: Using VS Code + PlatformIO (ADVANCED)

### 1. Install PlatformIO Extension
- Open VSCode
- **Extensions → Search "PlatformIO"**
- Install by PlatformIO

### 2. Create Project
- **PlatformIO Home → Create New Project**
- Name: `BP_Monitor`
- Board: `Espressif ESP32 Dev Module`
- Framework: `Arduino`

### 3. Copy Code
- Replace `src/main.cpp` with content from `bp_monitor_esp32.ino`

### 4. Add Library
Edit `platformio.ini`:
```ini
lib_deps = 
    ArduinoJson
```

### 5. Upload
- Click **Upload** (checkmark with arrow, bottom)

---

## Step 7: Verify It Works

### Check Serial Monitor
1. Arduino IDE: **Tools → Serial Monitor**
2. Set baud to **115200**
3. You should see:
   ```
   BP Monitor Reader Started
   Waiting for measurement...
   ```

### Run Python Test
```bash
cd /home/pi/Desktop/New/ArogyaVision
python3 test_bp_connection.py
```

Expected:
```
Scanning /dev/ttyUSB0 at 115200 baud...
✅ /dev/ttyUSB0 appears to be the BP monitor!

Results for /dev/ttyUSB0:
  Lines received: 5
  Valid JSON lines: 1 ✓
  Sample: {"sys": 120, "dia": 80, "pulse": 70, "status": "completed"}
```

---

## Troubleshooting

### Problem: Port not showing in Arduino IDE
**Solution:**
```bash
# Linux: Install CH340 driver
sudo apt install arduino-mk
# Or add user to dialout group:
sudo usermod -aG dialout $USER
# Restart terminal
```

### Problem: Upload fails with "No Board Found"
**Solution:**
- Try different USB port in **Tools → Port**
- Try lower upload speed: 115200 → 9600
- Hold BOOT button on ESP32 while uploading

### Problem: Serial Monitor shows garbage
**Solution:**
- Check baud rate is **115200**
- Check USB cable connection
- Try different USB port

### Problem: Still showing old format "Data=00045"
**Solution:**
- Verify you uploaded to the **CORRECT** ESP32 (BP monitor, not vitals)
- Check Upload button completed without errors
- Try uploading again

---

## Next Steps

After successful upload, run Streamlit app:
```bash
cd /home/pi/Desktop/New/ArogyaVision
streamlit run app.py
```

Then complete a full screening:
1. ✅ Start vitals scan (20 sec)
2. ✅ Confirm vitals
3. ✅ **BP Measurement (30 sec)** ← Should now show real values!
4. ✅ Confirm BP
5. ✅ Answer symptoms
6. ✅ Get diagnosis report
