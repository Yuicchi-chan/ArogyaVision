
# 🩺 ArogyaVision

ArogyaVision is a comprehensive health monitoring system that integrates hardware-based vitals tracking with an interactive web dashboard. It features live blood pressure monitoring via ESP32, a Streamlit-based user interface, and Text-to-Speech (TTS) capabilities.

## ✨ Features

* **Hardware Integration:** Real-time blood pressure and vitals monitoring using ESP32 (`bp_monitor_esp32.ino`).
* **Interactive Dashboard:** A responsive web application built with [Streamlit](https://streamlit.io/) (`app.py`).
* **Text-to-Speech (TTS):** Integrated audio feedback and assistance.
* **Diagnostics & Testing:** Robust testing suite for API endpoints, BP hardware connections, and live parsing.
* **Local Storage:** SQLite database integration for saving vital records (`arogya_vision.db`).

## 📂 Repository Structure

* `app.py` - Main Streamlit application file.
* `bp_monitor_esp32.ino` - Firmware for the ESP32 blood pressure monitoring hardware.
* `start_arogya.sh` / `start_arogya_tts.sh` - Bash scripts for easily launching the application.
* `diagnostic_bp.py` & `test_bp_*.py` - Diagnostic tools and parsers for the hardware monitor.
* `arogya_vision.db` - Local SQLite database.
* `Documentation/` - Project documentation and guides.

## 🚀 Getting Started

### Prerequisites
* Python 3.8+
* [Arduino IDE](https://www.arduino.cc/en/software) (for flashing the ESP32)
* Ensure you have your `env` (virtual environment) set up.

### Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/Yuicchi-chan/ArogyaVision.git](https://github.com/Yuicchi-chan/ArogyaVision.git)
   cd ArogyaVision

```

2. **Activate the virtual environment:**
*(Assuming the environment is in the `env` folder)*
```bash
source env/bin/activate  # On Linux/macOS
# OR
.\env\Scripts\activate   # On Windows

```


3. **Install dependencies:**
```bash
pip install -r requirements.txt

```


*(Note: Ensure you have a requirements.txt file generated if you haven't already!)*

### Running the Application

You can start the application using the provided shell scripts:

```bash
# Standard startup
bash start_arogya.sh

# Startup with Text-to-Speech enabled
bash start_arogya_tts.sh

```

Alternatively, you can run the Streamlit app directly:

```bash
streamlit run app.py

```

## 🔌 Hardware Setup (ESP32)

1. Open `bp_monitor_esp32.ino` in the Arduino IDE.
2. Connect your ESP32 board via USB.
3. Select the appropriate COM port and board type.
4. Compile and upload the sketch to the ESP32.
5. Use `test_bp_connection.py` and `test_bp_live.py` to verify the hardware is communicating correctly with the Python backend.
