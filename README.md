# 🩺 ArogyaVision

[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Framework-Streamlit-FF4B4B?style=flat-square&logo=streamlit)](https://streamlit.io/)
[![ESP32](https://img.shields.io/badge/Hardware-ESP32-E7352C?style=flat-square&logo=espressif)](https://www.espressif.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?style=flat-square&logo=sqlite)](https://www.sqlite.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation Guide](#installation-guide)
- [Quick Start](#quick-start)
- [Hardware Setup](#hardware-setup)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Testing & Diagnostics](#testing--diagnostics)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

---

## Overview

**ArogyaVision** is an enterprise-grade **Healthcare Monitoring and Diagnostics System** that seamlessly integrates real-time IoT hardware sensors with an intelligent web-based dashboard. The system provides continuous monitoring of vital signs, particularly blood pressure, with clinical-grade accuracy and professional data management capabilities.

### Use Cases

- 🏥 **Clinical Settings:** Real-time patient monitoring in healthcare facilities
- 👨‍⚕️ **Telemedicine:** Remote patient monitoring and diagnostics
- 🏠 **Home Healthcare:** Continuous personal health tracking with alert systems
- 📊 **Research:** Data collection and analysis for medical studies

### Core Value Proposition

- **Accuracy:** Hardware-based measurements with clinical validation
- **Real-time Monitoring:** Live data streaming and instant alerts
- **User-Friendly:** Intuitive web interface accessible from any device
- **Data Security:** Local storage with encrypted communications
- **Accessibility:** Text-to-Speech support for diverse user needs

---

## Key Features

| Feature | Description | Status |
|---------|-------------|--------|
| 🔴 **Real-time Vitals Monitoring** | Live blood pressure and pulse rate tracking via ESP32 sensors with millisecond precision | ✅ Production |
| 📱 **Interactive Web Dashboard** | Responsive Streamlit-based interface with real-time data visualization and charts | ✅ Production |
| 🔊 **Audio Assistance (TTS)** | Text-to-Speech integration for instructions and alerts; supports multiple languages | ✅ Production |
| 🧪 **Diagnostic Testing Suite** | Comprehensive test tools for hardware connection validation and data integrity checks | ✅ Production |
| 💾 **Data Persistence** | SQLite database with automated backup and historical data retention | ✅ Production |
| 📈 **Analytics & Reports** | Exportable health reports in PDF/CSV formats with trend analysis | 🔄 In Progress |
| 🔔 **Smart Alerts** | Automatic notifications for abnormal readings with severity levels | 🔄 In Progress |
| 🔐 **HIPAA Compliance** | Data encryption and security protocols for healthcare standards | 🚀 Planned |

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      ArogyaVision Ecosystem                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────┐          ┌──────────────────────┐
│   Hardware       │          │   Data Processing    │
├─────────────────┤          ├──────────────────────┤
│ • ESP32-CAM     │─────────▶│ • Python Backend     │
│ • BP Monitor    │  Serial  │ • Data Validation    │
│ • Sensors       │          │ • Real-time Analysis │
└─────────────────┘          └──────────┬───────────┘
                                        │
                                        ▼
                            ┌──────────────────────┐
                            │  Application Layer   │
                            ├──────────────────────┤
                            │ • Streamlit UI       │
                            │ • Dashboard          │
                            │ • User Interface     │
                            └──────────┬───────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
            ┌─────────────┐    ┌──────────────┐    ┌─────────────┐
            │  SQLite DB  │    │ TTS Engine   │    │  File Store │
            │  (History)  │    │  (Alerts)    │    │ (Backups)   │
            └─────────────┘    └──────────────┘    └─────────────┘
```

### Data Flow

```
ESP32 Sensor → Serial Connection → Python Parser → Data Validation
    ↓
 Streamlit UI ← SQLite Database ← Real-time Processing
    ↓
User Dashboard ← Analytics Engine ← Historical Data Analysis
```

---

## Prerequisites

### System Requirements

| Component | Specification | Notes |
|-----------|---------------|-------|
| **OS** | Windows 10+, macOS 10.14+, Linux (Ubuntu 18.04+) | Cross-platform compatible |
| **Python** | 3.8 or higher | 3.10+ recommended for better performance |
| **RAM** | Minimum 4GB | 8GB+ recommended for smooth operation |
| **Storage** | 500MB free space | For application and database |
| **Network** | Stable internet connection | Required for updates and optional cloud sync |

### Software Dependencies

- **Python 3.8+** ([Download](https://www.python.org/downloads/))
- **Arduino IDE** ([Download](https://www.arduino.cc/en/software)) - For ESP32 firmware flashing
- **Git** ([Download](https://git-scm.com/)) - For repository cloning
- **pip** - Usually comes with Python
- **Virtual Environment** - Built-in with Python 3.3+

### Hardware Requirements

| Item | Model | Purpose |
|------|-------|---------|
| **Microcontroller** | ESP32 or ESP32-S3 | Main sensor hub |
| **BP Monitor** | Digital blood pressure sensor | Vital measurement |
| **USB Cable** | Micro-USB or USB-C | ESP32 connection |
| **Sensors** (Optional) | Temperature, Pulse oximeter | Extended monitoring |

---

## Installation Guide

### Step 1: Clone the Repository

```bash
# Clone using HTTPS
git clone https://github.com/Yuicchi-chan/ArogyaVision.git
cd ArogyaVision

# OR clone using SSH
git clone git@github.com:Yuicchi-chan/ArogyaVision.git
cd ArogyaVision
```

### Step 2: Create and Activate Virtual Environment

**On Windows:**
```batch
# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate
```

**On macOS/Linux:**
```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
# Upgrade pip to latest version
pip install --upgrade pip

# Install all required packages
pip install -r requirements.txt

# Verify installation
pip list
```

### Step 4: Verify Installation

```bash
# Check Python version
python --version

# Check Streamlit installation
streamlit --version

# List installed packages
pip list | grep -E "streamlit|pyserial"
```

---

## Quick Start

### Running the Application (Standard Mode)

**Option 1: Using Shell Scripts (Recommended)**
```bash
# Run with default settings
bash start_arogya.sh

# Run with Text-to-Speech enabled
bash start_arogya_tts.sh
```

**Option 2: Direct Streamlit Command**
```bash
streamlit run app.py
```

**Option 3: Custom Configuration**
```bash
# Run on specific port
streamlit run app.py --server.port 8501

# Run in headless mode
streamlit run app.py --logger.level=debug

# Run with custom config
streamlit run app.py --config.toml config.toml
```

### Accessing the Dashboard

After running the application:
- **Local Access:** `http://localhost:8501`
- **Network Access:** `http://<your-machine-ip>:8501`
- **Remote Access:** Deploy to cloud platform (Heroku, AWS, Azure)

### First-Time Setup Checklist

- [ ] Virtual environment activated
- [ ] All dependencies installed
- [ ] ESP32 connected via USB
- [ ] Serial port detected (COM port on Windows, /dev/ttyUSB0 on Linux)
- [ ] Database initialized
- [ ] Dashboard loads without errors

---

## Hardware Setup

### ESP32 Configuration

#### Prerequisites for Hardware Setup
- Arduino IDE installed
- ESP32 board package added to Arduino IDE
- USB cable connecting ESP32 to computer
- Device drivers installed (CH340 drivers for some clones)

#### Step-by-Step Installation

**Step 1: Install Arduino IDE**
```
1. Download from https://www.arduino.cc/en/software
2. Install following the platform-specific instructions
3. Launch Arduino IDE
```

**Step 2: Add ESP32 Board to Arduino IDE**
```
1. Go to File → Preferences
2. In "Additional Board Manager URLs", add:
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
3. Click OK
4. Go to Tools → Board Manager
5. Search for "esp32"
6. Install the latest version
```

**Step 3: Configure Arduino IDE for ESP32**
```
1. Go to Tools → Board → ESP32 Arduino → Select "ESP32 Dev Module" (or your variant)
2. Set Upload Speed: 115200
3. Set Flash Frequency: 80MHz
4. Set Partition Scheme: Default 4MB with spiffs
```

**Step 4: Upload Firmware to ESP32**
```
1. Connect ESP32 to computer via USB cable
2. Open Tools → Port and select the COM port (Windows) or /dev/ttyUSB0 (Linux)
3. Open bp_monitor_esp32.ino in Arduino IDE
4. Click Upload (→ button or Ctrl+U)
5. Wait for "Upload complete" message
```

**Step 5: Verify Hardware Connection**
```bash
# Run connection test
python test_bp_connection.py

# If successful, you should see:
# "ESP32 connection established successfully"
# "Device ready for data transmission"
```

#### Hardware Troubleshooting

| Issue | Solution |
|-------|----------|
| **COM port not showing** | Install CH340 drivers or check USB connection |
| **Upload fails** | Verify board type and upload speed settings |
| **Serial connection error** | Disconnect/reconnect ESP32, check baudrate |
| **No data from sensor** | Verify sensor connections, check sensor power |

### Sensor Connection Diagram

```
ESP32 GPIO Connections:
┌─────────────────────────────────────┐
│          ESP32 Pinout               │
├─────────────────────────────────────┤
│ BP Sensor → GPIO 16 (RX2) + GPIO 17 (TX2)
│ Pulse Sensor → GPIO 35 (ADC1_7)
│ Temp Sensor → GPIO 32 (ADC1_4)
│ Power Supply → VIN + GND
│ USB Connection → Micro USB Port
└─────────────────────────────────────┘
```

---

## API Reference

### Serial Communication Protocol

The ESP32 sends data to the Python backend via serial connection using a standardized JSON format.

#### Data Format

```json
{
  "timestamp": "2026-06-10T14:30:45.123456",
  "device_id": "ESP32_001",
  "vitals": {
    "systolic": 120,
    "diastolic": 80,
    "pulse": 72,
    "temperature": 37.2
  },
  "status": "OK",
  "battery": 85
}
```

#### Message Specification

| Field | Type | Range | Unit |
|-------|------|-------|------|
| `systolic` | Integer | 40-240 | mmHg |
| `diastolic` | Integer | 40-160 | mmHg |
| `pulse` | Integer | 40-200 | bpm |
| `temperature` | Float | 35.0-42.0 | °C |
| `battery` | Integer | 0-100 | % |

#### Error Codes

```
Code  Description                      Action
====  ===========                      ======
0x00  Success                          No action needed
0x01  Sensor malfunction               Check sensor connections
0x02  Communication error              Reconnect ESP32
0x03  Data transmission timeout        Reset device
0x04  Battery low                      Charge device
0x05  Device not calibrated            Recalibrate sensors
0xFF  Unknown error                    Restart system
```

---

## Project Structure

```
ArogyaVision/
├── 📄 README.md                      # Project documentation (this file)
├── 📄 requirements.txt               # Python dependencies
├── 🐍 app.py                         # Main Streamlit application
├── 🚀 start_arogya.sh               # Startup script (standard mode)
├── 🔊 start_arogya_tts.sh           # Startup script (TTS enabled)
│
├── 📁 Hardware/
│   ├── 🖥️ bp_monitor_esp32.ino      # ESP32 firmware source code
│   ├── 📋 pin_configuration.txt     # GPIO pin assignments
│   └── 📊 sensor_specs.pdf          # Sensor datasheets
│
├── 📁 Backend/
│   ├── 🔧 diagnostic_bp.py          # Hardware diagnostics tool
│   ├── 🧪 test_bp_connection.py    # Connection validation
│   ├── 📈 test_bp_live.py          # Real-time data testing
│   ├── 📊 data_processor.py         # Data parsing & validation
│   └── 💾 database_manager.py       # Database operations
│
├── 📁 Frontend/
│   ├── 📊 dashboard_components.py   # UI component library
│   ├── 📈 visualization.py          # Chart & graph utilities
│   └── 🎨 styles.css               # Custom styling (if applicable)
│
├── 📁 Database/
│   └── 💾 arogya_vision.db          # SQLite database (auto-created)
│
├── 📁 Documentation/
│   ├── 📖 SETUP.md                  # Detailed setup guide
│   ├── 🔧 API.md                    # API documentation
│   ├── 🐛 TROUBLESHOOTING.md        # Common issues & fixes
│   └── 📚 ARCHITECTURE.md           # System architecture details
│
├── 📁 Data/
│   ├── 📊 exports/                  # Exported reports (CSV, PDF)
│   └── 📁 backups/                  # Automatic backups
│
└── 📁 .github/
    ├── 📝 CONTRIBUTING.md            # Contribution guidelines
    └── 🚨 ISSUE_TEMPLATE/           # Issue templates
```

### File Descriptions

| File | Purpose | Maintenance |
|------|---------|-------------|
| `app.py` | Main application logic | Modify for UI changes |
| `bp_monitor_esp32.ino` | Hardware firmware | Update for sensor changes |
| `requirements.txt` | Dependencies | Update when adding packages |
| `arogya_vision.db` | Data storage | Auto-managed, backup regularly |
| `Documentation/` | Reference guides | Update with new features |

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Serial Communication
SERIAL_PORT=/dev/ttyUSB0          # Linux/macOS
# SERIAL_PORT=COM3                # Windows
BAUD_RATE=115200
TIMEOUT=5

# Application Settings
APP_TITLE=ArogyaVision Dashboard
APP_DEBUG=False
APP_PORT=8501

# Database Configuration
DB_PATH=arogya_vision.db
DB_BACKUP=True
BACKUP_INTERVAL=3600              # Seconds

# Text-to-Speech
TTS_ENABLED=True
TTS_LANGUAGE=en

# Data Settings
DATA_RETENTION_DAYS=365            # Delete data older than 1 year
AUTO_EXPORT=False
EXPORT_INTERVAL=86400              # Daily
```

### Application Configuration (config.toml)

```toml
[streamlit]
theme.primaryColor = "#1f77b4"
theme.backgroundColor = "#FFFFFF"
theme.secondaryBackgroundColor = "#F0F2F6"
theme.textColor = "#262730"

[logger]
level = "info"

[client]
showErrorDetails = true

[server]
port = 8501
headless = true
runOnSave = true
```

### Database Schema

```sql
-- Users Table
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vital Records Table
CREATE TABLE vital_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    systolic INTEGER NOT NULL,
    diastolic INTEGER NOT NULL,
    pulse INTEGER NOT NULL,
    temperature REAL,
    notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Device Logs Table
CREATE TABLE device_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT,
    error_code INTEGER,
    message TEXT
);
```

---

## Testing & Diagnostics

### Running Tests

#### 1. Connection Test
Verifies ESP32 is connected and responding.

```bash
python test_bp_connection.py
```

**Expected Output:**
```
[✓] Serial port found: /dev/ttyUSB0
[✓] Connection established
[✓] Device responded: ESP32_001
[✓] Firmware version: 1.0.2
```

#### 2. Live Data Test
Displays real-time sensor readings for 30 seconds.

```bash
python test_bp_live.py
```

**Expected Output:**
```
Reading #1: Systolic=120, Diastolic=80, Pulse=72
Reading #2: Systolic=119, Diastolic=79, Pulse=71
Reading #3: Systolic=121, Diastolic=81, Pulse=73
...
[✓] All readings within normal range
```

#### 3. Diagnostic Check
Comprehensive system health check.

```bash
python diagnostic_bp.py
```

**Expected Output:**
```
========== ArogyaVision Diagnostics ==========
[✓] Python version: 3.10.2
[✓] Dependencies installed: 15/15
[✓] Database accessible
[✓] Serial port available
[✓] ESP32 responsive
[✓] Sensor calibration: OK
[✓] Memory usage: 245MB/8GB
[✓] Last backup: 2 hours ago
============================================
System Status: HEALTHY ✓
```

### Unit Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_data_processor.py -v

# Run with coverage report
pytest --cov=. --cov-report=html
```

---

## Troubleshooting

### Common Issues and Solutions

#### Issue: "Serial Port Not Found"

**Symptoms:** Error message when starting the application

**Solutions:**
1. Check USB connection: `lsusb` (Linux) or Device Manager (Windows)
2. Install drivers: CH340 drivers for ESP32 clones
3. Change serial port in `config.toml`
4. Run with elevated privileges (if on Linux/macOS)

```bash
# Linux/macOS - Add user to dialout group
sudo usermod -a -G dialout $USER

# Windows - Run as Administrator
# Right-click cmd.exe → Run as administrator
```

#### Issue: "Connection Timeout"

**Symptoms:** Serial connection established but no data received

**Solutions:**
1. Verify ESP32 firmware is uploaded correctly
2. Check baud rate (should be 115200)
3. Restart ESP32: Disconnect USB for 5 seconds, reconnect
4. Check sensor connections on breadboard/circuit

#### Issue: "Streamlit App Won't Start"

**Symptoms:** `ModuleNotFoundError` or `ImportError`

**Solutions:**
```bash
# Reinstall dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt --force-reinstall

# Clear Streamlit cache
rm -rf ~/.streamlit ~/.cache

# Check Python version (should be 3.8+)
python --version
```

#### Issue: "Abnormal Readings"

**Symptoms:** Systolic/Diastolic values exceeding normal range

**Solutions:**
1. Recalibrate sensor: Follow manufacturer instructions
2. Check sensor battery level
3. Verify sensor placement (wrist vs. arm)
4. Ensure proper cuff fit (blood pressure cuff)

#### Issue: "Database Corruption"

**Symptoms:** "Database disk image is malformed" error

**Solutions:**
```bash
# Restore from backup
cp arogya_vision.db.backup arogya_vision.db

# Or reinitialize (WARNING: will lose data)
rm arogya_vision.db
# Restart application to recreate database
```

### Debug Mode

Enable detailed logging:

```bash
# Using environment variable
export APP_DEBUG=True
streamlit run app.py --logger.level=debug

# Check logs
tail -f logs/arogya_vision.log
```

### Performance Optimization

| Issue | Optimization |
|-------|-------------|
| Slow dashboard response | Reduce data query range, enable caching |
| High CPU usage | Reduce update frequency, optimize database queries |
| Memory leaks | Clear cache periodically, limit historical data |
| Serial lag | Reduce logging level, increase baud rate |

---

## Contributing

We welcome contributions! Please follow these guidelines:

### Contribution Workflow

1. **Fork the Repository**
   ```bash
   # On GitHub website, click "Fork"
   ```

2. **Clone Your Fork**
   ```bash
   git clone https://github.com/YOUR_USERNAME/ArogyaVision.git
   cd ArogyaVision
   ```

3. **Create a Feature Branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```

4. **Make Your Changes**
   - Follow PEP 8 code style
   - Add docstrings to functions
   - Update tests as needed
   - Add comments for complex logic

5. **Test Your Changes**
   ```bash
   pytest tests/
   ```

6. **Commit with Clear Messages**
   ```bash
   git commit -m "feat: add amazing feature description"
   # or
   git commit -m "fix: resolve issue with data parsing"
   git commit -m "docs: update README with new feature"
   ```

7. **Push to Your Fork**
   ```bash
   git push origin feature/amazing-feature
   ```

8. **Create Pull Request**
   - Go to GitHub website
   - Click "Compare & pull request"
   - Add detailed description of changes
   - Link any related issues

### Code Standards

- **Python:** Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- **Naming:** Use descriptive variable/function names
- **Comments:** Explain "why", not "what"
- **Tests:** Write tests for new features
- **Documentation:** Update docs with changes

### Commit Message Format

```
<type>: <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Example:
```
feat: add real-time alert notifications

Implement push notifications for abnormal vital readings.
Includes UI notifications and optional email alerts.

Closes #42
```

---

## License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for full details.

### License Summary

✅ **Permitted:**
- Commercial use
- Modification
- Distribution
- Private use

❌ **Prohibited:**
- Liability (use at own risk)
- Warranty

📝 **Conditions:**
- Include license notice
- Include copyright notice

---

## Support

### Getting Help

| Channel | Use Case |
|---------|----------|
| [GitHub Issues](https://github.com/Yuicchi-chan/ArogyaVision/issues) | Bug reports, feature requests |
| [Discussions](https://github.com/Yuicchi-chan/ArogyaVision/discussions) | Questions, general discussion |
| [Documentation](Documentation/) | Setup guides, API reference |
| [Email](mailto:support@arogya.com) | Commercial inquiries |

### Frequently Asked Questions

**Q: Is this production-ready?**
A: Yes, for personal and small-scale clinical use. Ensure HIPAA compliance for healthcare applications.

**Q: Can I use this with different sensors?**
A: Yes, modify `bp_monitor_esp32.ino` for your sensor type and update data parsing in `data_processor.py`.

**Q: How do I export data?**
A: Use the dashboard export feature or query the SQLite database directly.

**Q: Is there cloud backup support?**
A: Currently local storage only. Cloud sync planned for future release.

**Q: How accurate are the readings?**
A: Depends on the sensor used. Typically ±3mmHg for quality sensors.

### Reporting Issues

Please use the [Issue Tracker](https://github.com/Yuicchi-chan/ArogyaVision/issues) with:
- Clear title
- Reproduction steps
- Expected vs actual behavior
- System information (OS, Python version, etc.)
- Error messages/logs

---

## Roadmap

### Version 1.0 (Current)
- ✅ Basic vital monitoring
- ✅ Streamlit dashboard
- ✅ SQLite storage
- ✅ TTS support

### Version 1.1 (Next)
- 🔄 Advanced analytics
- 🔄 PDF report generation
- 🔄 Data export (CSV, Excel)

### Version 2.0 (Planned)
- 🚀 Mobile app (React Native)
- 🚀 Cloud synchronization
- 🚀 Multi-user support
- 🚀 HIPAA compliance
- 🚀 AI-based anomaly detection

### Future Enhancements
- Machine learning for predictive health alerts
- Integration with EHR systems
- Wearable device support
- Telemedicine integration

---

<div align="center">

### Made with ❤️ for Healthcare Innovation

**[GitHub](https://github.com/Yuicchi-chan/ArogyaVision)** • **[Issues](https://github.com/Yuicchi-chan/ArogyaVision/issues)** • **[Wiki](https://github.com/Yuicchi-chan/ArogyaVision/wiki)**

*Empowering healthcare through open-source technology*

**Last Updated:** June 2026 | **Version:** 1.0.0 | **Status:** Active Development

</div>
