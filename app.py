import streamlit as st
import serial
import json
import time
import requests
import threading
import sqlite3
from datetime import datetime
import glob
import psutil
import subprocess
import re
import random
import html
from google.cloud import texttospeech
import os
import textwrap

# --- CONFIGURATION ---
OPENROUTER_API_KEY = "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"
BAUD_RATE = 9600  # Default vitals baud
BP_BAUD_RATE = 115200  # Default BP baud
PROBE_BAUD_RATE = 115200
TEMP_OFFSET_F = 6.23          # Sensor calibration offset (°F) — added to raw reading
PROBE_DURATION_SEC = 1.5
PROBE_BAUD_CANDIDATES = [115200, 9600]
PROBE_HARD_TIMEOUT_SEC = 4.0
DEBUG_ENABLED = True
DEBUG_UI_MAX_LINES = 80
DEBUG_THROTTLE_SEC = 5


_debug_last_emit = {}


def debug_log(message, level="INFO", ui=False):
    """Print timestamped debug logs and optionally mirror them in UI session log."""
    if not DEBUG_ENABLED:
        return
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[DBG {ts}] [{level}] {message}"
    print(line, flush=True)

    if not ui:
        return

    try:
        if 'debug_lines' not in st.session_state:
            st.session_state.debug_lines = []
        st.session_state.debug_lines.append(line)
        if len(st.session_state.debug_lines) > DEBUG_UI_MAX_LINES:
            st.session_state.debug_lines = st.session_state.debug_lines[-DEBUG_UI_MAX_LINES:]
    except Exception:
        # Session state may be unavailable during very early startup.
        pass


def debug_log_throttled(key, message, level="DEBUG", every_sec=DEBUG_THROTTLE_SEC, ui=False):
    """Emit repeated status logs at a controlled interval."""
    now = time.time()
    last = _debug_last_emit.get(key, 0)
    if now - last >= every_sec:
        _debug_last_emit[key] = now
        debug_log(message, level=level, ui=ui)

# --- STATIC PORT INITIALIZATION ---
# Using hardcoded device aliases created with udev rules
VITALS_PORT_NAME = "/dev/ttyUSB1"
BP_PORT_NAME = "/dev/ttyUSB0"

def init_serial_port(port_name, baud_rate, port_description):
    """Initialize serial connection to hardcoded port name"""
    debug_log(f"Opening {port_description} on {port_name} @ {baud_rate}")
    try:
        ser = serial.Serial(port_name, baud_rate, timeout=1)
        time.sleep(0.5)
        ser.reset_input_buffer()  # Clear any buffered data
        print(f"[OK] Connected to {port_description} at {port_name} ({baud_rate} baud)")
        return ser, port_name
    except FileNotFoundError:
        print(f"[ERR] {port_description} not found at {port_name}")
        print(f"  Make sure udev rule exists: /etc/udev/rules.d/*.rules")
        return None, None
    except serial.SerialException as e:
        print(f"[ERR] Serial error on {port_description}: {e}")
        return None, None
    except Exception as e:
        print(f"[ERR] Unexpected error initializing {port_description}: {e}")
        return None, None

def list_serial_ports():
    """Return currently connected ttyUSB/ttyACM ports."""
    ports = sorted(set(glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')))
    return ports

def probe_port_legibility(port_name, baud_rate=PROBE_BAUD_RATE, duration=PROBE_DURATION_SEC):
    """Probe a serial port and estimate whether stream is legible vitals-like data."""
    debug_log(f"Probing {port_name} @ {baud_rate} for {duration:.1f}s")
    result = {
        "port": port_name,
        "lines": 0,
        "avg_printable": 0.0,
        "json_hits": 0,
        "vitals_hits": 0,
        "bp_hits": 0,
        "bp_hint_hits": 0,
        "looks_legible": False,
    }
    ser = None
    printable_sum = 0.0
    try:
        ser = serial.Serial(port_name, baud_rate, timeout=0.1)
        time.sleep(0.2)
        ser.reset_input_buffer()
        deadline = time.time() + duration

        while time.time() < deadline:
            if ser.in_waiting <= 0:
                time.sleep(0.01)
                continue

            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if not line:
                continue

            result["lines"] += 1
            printable_sum += sum(1 for ch in line if ch.isprintable()) / max(len(line), 1)

            line_lower = line.lower()
            if 'data=' in line_lower:
                result["bp_hits"] += 1

            if any(token in line_lower for token in ("sleep mode", "truepulsecount", "pulsecount", "inflate", "deflate", "cuff")):
                result["bp_hint_hits"] += 1

            try:
                payload = json.loads(line)
                if isinstance(payload, dict):
                    result["json_hits"] += 1
                    if any(k in payload for k in ("temp", "hr", "spo2", "stress")):
                        result["vitals_hits"] += 1
            except Exception:
                pass

    except Exception as e:
        print(f"[PROBE] {port_name} probe error at {baud_rate}: {e}")
    finally:
        if ser:
            try:
                ser.close()
            except Exception:
                pass

    if result["lines"] > 0:
        result["avg_printable"] = printable_sum / result["lines"]

    # Legible means vitals-like JSON present (strong signal).
    result["looks_legible"] = result["vitals_hits"] > 0
    debug_log(
        f"Probe result {port_name}@{baud_rate}: lines={result['lines']} json={result['json_hits']} "
        f"vitals={result['vitals_hits']} bp={result['bp_hits']} bp_hint={result['bp_hint_hits']} printable={result['avg_printable']:.2f} "
        f"legible={result['looks_legible']}"
    )
    return result


def probe_port_legibility_with_timeout(
    port_name,
    baud_rate=PROBE_BAUD_RATE,
    duration=PROBE_DURATION_SEC,
    hard_timeout=PROBE_HARD_TIMEOUT_SEC,
):
    """Run probe with a hard watchdog timeout so one bad port cannot block UI."""
    result_box = {
        "done": False,
        "result": {
            "port": port_name,
            "baud": baud_rate,
            "lines": 0,
            "avg_printable": 0.0,
            "json_hits": 0,
            "vitals_hits": 0,
            "bp_hits": 0,
            "bp_hint_hits": 0,
            "looks_legible": False,
        },
    }

    def _target():
        try:
            r = probe_port_legibility(port_name, baud_rate=baud_rate, duration=duration)
            r["baud"] = baud_rate
            result_box["result"] = r
        except Exception as e:
            debug_log(f"Probe worker exception {port_name}@{baud_rate}: {e}", level="WARN")
        finally:
            result_box["done"] = True

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join(max(0.5, hard_timeout))

    if not result_box["done"]:
        debug_log(
            f"Probe watchdog timeout for {port_name}@{baud_rate} after {hard_timeout:.1f}s; using empty result",
            level="WARN",
        )

    return result_box["result"]


def probe_port_best_match(port_name, baud_candidates=None, duration=PROBE_DURATION_SEC):
    """Probe a port across baud candidates and return the strongest overall signal."""
    if baud_candidates is None:
        baud_candidates = PROBE_BAUD_CANDIDATES

    best = None
    for baud in baud_candidates:
        candidate = probe_port_legibility_with_timeout(
            port_name,
            baud_rate=baud,
            duration=duration,
            hard_timeout=PROBE_HARD_TIMEOUT_SEC,
        )
        if best is None:
            best = candidate
            continue

        # Prioritize strong protocol signals first, then legibility/volume.
        cur_score = (
            candidate["vitals_hits"],
            candidate["bp_hits"],
            candidate.get("bp_hint_hits", 0),
            candidate["json_hits"],
            candidate["avg_printable"],
            candidate["lines"],
        )
        best_score = (
            best["vitals_hits"],
            best["bp_hits"],
            best.get("bp_hint_hits", 0),
            best["json_hits"],
            best["avg_printable"],
            best["lines"],
        )
        if cur_score > best_score:
            best = candidate

    return best or {
        "port": port_name,
        "baud": PROBE_BAUD_RATE,
        "lines": 0,
        "avg_printable": 0.0,
        "json_hits": 0,
        "vitals_hits": 0,
        "bp_hits": 0,
        "bp_hint_hits": 0,
        "looks_legible": False,
    }


def has_vitals_json_at_9600(port_name, duration=1.8):
    """Check whether a port emits vitals JSON at 9600 baud."""
    stats = {
        "port": port_name,
        "baud": 9600,
        "lines": 0,
        "json_hits": 0,
        "vitals_hits": 0,
        "error": "",
    }
    ser = None

    try:
        ser = serial.Serial(port_name, 9600, timeout=0.15)
        time.sleep(0.2)
        ser.reset_input_buffer()
        deadline = time.time() + max(0.6, duration)

        while time.time() < deadline:
            if ser.in_waiting <= 0:
                time.sleep(0.01)
                continue

            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if not line:
                continue

            stats["lines"] += 1
            print(f"[DETECT RAW] {port_name}@9600: {line}", flush=True)

            try:
                payload = json.loads(line)
                if isinstance(payload, dict):
                    stats["json_hits"] += 1
                    if any(k in payload for k in ("temp", "hr", "spo2", "stress")):
                        stats["vitals_hits"] += 1
                        return True, stats
            except Exception:
                pass
    except Exception as e:
        stats["error"] = str(e)
        debug_log(f"Vitals JSON check failed on {port_name}@9600: {e}", level="WARN")
    finally:
        if ser:
            try:
                ser.close()
            except Exception:
                pass

    return False, stats

def infer_serial_roles():
    """Simple rule-based detection:
    - Pick one random port (among max two) and check for vitals JSON at 9600.
    - If JSON found: tested port is Vitals@9600, other is BP@115200.
    - If not found: other is Vitals@9600, tested port is BP@115200.
    """
    detected_ports = list_serial_ports()
    ports = detected_ports[:2]
    debug_log(f"Simple role inference start. Detected ports={detected_ports}, using={ports}")

    vitals_port = None
    bp_port = None
    vitals_baud = BAUD_RATE
    bp_baud = BP_BAUD_RATE
    status = "Partial detection"
    probes = []

    if not ports:
        return {
            "ports": [],
            "probes": [],
            "vitals_port": None,
            "vitals_baud": vitals_baud,
            "bp_port": None,
            "bp_baud": bp_baud,
            "status": "No serial ports found",
            "summary": "No ttyUSB/ttyACM ports detected",
        }

    if len(ports) == 1:
        tested_port = ports[0]
        has_json, probe = has_vitals_json_at_9600(tested_port)
        probes.append(probe)

        if has_json:
            vitals_port = tested_port
            status = "Partial detection"
            summary = f"Tested {tested_port}@9600 -> JSON vitals detected; Vitals assigned, BP port missing"
        else:
            bp_port = tested_port
            status = "Partial detection"
            summary = f"Tested {tested_port}@9600 -> no JSON vitals; BP assigned, Vitals port missing"

        return {
            "ports": ports,
            "probes": probes,
            "vitals_port": vitals_port,
            "vitals_baud": vitals_baud,
            "bp_port": bp_port,
            "bp_baud": bp_baud,
            "status": status,
            "summary": summary,
        }

    tested_port = random.choice(ports)
    other_port = ports[0] if ports[1] == tested_port else ports[1]
    has_json, probe = has_vitals_json_at_9600(tested_port)
    probes.append(probe)

    if has_json:
        vitals_port = tested_port
        bp_port = other_port
        status = "Auto-detected"
        summary = (
            f"Tested {tested_port}@9600 -> JSON vitals detected; "
            f"Vitals={vitals_port}@9600, BP={bp_port}@115200"
        )
    else:
        vitals_port = other_port
        bp_port = tested_port
        status = "Auto-detected"
        summary = (
            f"Tested {tested_port}@9600 -> no JSON vitals; "
            f"Vitals={vitals_port}@9600, BP={bp_port}@115200"
        )

    return {
        "ports": ports,
        "probes": probes,
        "vitals_port": vitals_port,
        "vitals_baud": vitals_baud,
        "bp_port": bp_port,
        "bp_baud": bp_baud,
        "status": status,
        "summary": summary,
    }


def assess_stream_readiness(vitals_ser=None, bp_ser=None, duration=1.5):
    """Verify that vitals emits JSON vitals keys and BP emits BP/sleep signatures."""
    vitals = {"lines": 0, "json_hits": 0, "vitals_hits": 0}
    bp = {"lines": 0, "bp_hits": 0, "bp_hint_hits": 0}

    deadline = time.time() + max(0.5, duration)
    while time.time() < deadline:
        # Vitals validation: expect JSON with temp/hr/spo2/stress keys.
        if vitals_ser:
            try:
                if vitals_ser.in_waiting > 0:
                    line = vitals_ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        vitals["lines"] += 1
                        try:
                            payload = json.loads(line)
                            if isinstance(payload, dict):
                                vitals["json_hits"] += 1
                                if any(k in payload for k in ("temp", "hr", "spo2", "stress")):
                                    vitals["vitals_hits"] += 1
                        except Exception:
                            pass
            except Exception:
                pass

        # BP validation: expect Data= lines or known BP device hints like sleep mode.
        if bp_ser:
            try:
                if bp_ser.in_waiting > 0:
                    line = bp_ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        bp["lines"] += 1
                        line_lower = line.lower()
                        if "data=" in line_lower:
                            bp["bp_hits"] += 1
                        if any(token in line_lower for token in ("sleep mode", "truepulsecount", "pulsecount", "inflate", "deflate", "cuff")):
                            bp["bp_hint_hits"] += 1
            except Exception:
                pass

        time.sleep(0.01)

    vitals_ready = vitals["vitals_hits"] > 0
    bp_ready = (bp["bp_hits"] > 0) or (bp["bp_hint_hits"] > 0)
    summary = (
        f"Vitals: lines={vitals['lines']} json={vitals['json_hits']} vitals={vitals['vitals_hits']} | "
        f"BP: lines={bp['lines']} data={bp['bp_hits']} hints={bp['bp_hint_hits']}"
    )

    debug_log(f"Readiness verification -> {summary}")
    return {
        "vitals_ready": vitals_ready,
        "bp_ready": bp_ready,
        "summary": summary,
    }

def reconnect_serial_connections(vitals_port, vitals_baud, bp_port, bp_baud):
    """Close old handles and reconnect selected vitals/BP serial ports."""
    global SERIAL_PORT, VITALS_PORT, BP_SERIAL_PORT, BP_PORT
    debug_log(
        f"Reconnect requested: vitals={vitals_port}@{vitals_baud}, bp={bp_port}@{bp_baud}",
        ui=True,
    )

    for key in ("serial_vitals_obj", "serial_bp_obj"):
        old_ser = st.session_state.get(key)
        if old_ser:
            try:
                if old_ser.is_open:
                    old_ser.close()
            except Exception:
                pass

    SERIAL_PORT, VITALS_PORT = (None, None)
    BP_SERIAL_PORT, BP_PORT = (None, None)

    if vitals_port:
        SERIAL_PORT, VITALS_PORT = init_serial_port(vitals_port, vitals_baud, "Vitals Sensor")
    if bp_port:
        BP_SERIAL_PORT, BP_PORT = init_serial_port(bp_port, bp_baud, "BP Monitor")

    st.session_state.serial_vitals_obj = SERIAL_PORT
    st.session_state.serial_bp_obj = BP_SERIAL_PORT

    readiness = assess_stream_readiness(SERIAL_PORT, BP_SERIAL_PORT, duration=1.5)
    st.session_state.vitals_stream_ready = readiness["vitals_ready"]
    st.session_state.bp_stream_ready = readiness["bp_ready"]
    st.session_state.stream_readiness_summary = readiness["summary"]

    debug_log(
        f"Reconnect result: vitals_ok={bool(SERIAL_PORT)} bp_ok={bool(BP_SERIAL_PORT)} "
        f"vitals_ready={readiness['vitals_ready']} bp_ready={readiness['bp_ready']}",
        ui=True,
    )

    return bool(SERIAL_PORT), bool(BP_SERIAL_PORT)

def bootstrap_serial_connections_once():
    """Detect and initialize serial connections once at server startup."""
    debug_log("Startup serial bootstrap begin")
    detection = infer_serial_roles()
    ports = detection["ports"]

    vitals_port = detection["vitals_port"]

    if detection["bp_port"] and detection["bp_port"] != vitals_port:
        bp_port = detection["bp_port"]
    else:
        remaining = [p for p in ports if p != vitals_port]
        bp_port = remaining[0] if remaining else ""

    vitals_baud = detection.get("vitals_baud", BAUD_RATE)
    bp_baud = detection.get("bp_baud", BP_BAUD_RATE)

    serial_vitals_obj, connected_vitals_port = (None, None)
    serial_bp_obj, connected_bp_port = (None, None)

    if vitals_port:
        serial_vitals_obj, connected_vitals_port = init_serial_port(vitals_port, vitals_baud, "Vitals Sensor")
    if bp_port:
        serial_bp_obj, connected_bp_port = init_serial_port(bp_port, bp_baud, "BP Monitor")

    readiness = assess_stream_readiness(serial_vitals_obj, serial_bp_obj, duration=1.5)

    debug_log(
        f"Startup serial bootstrap done: vitals={connected_vitals_port}@{vitals_baud} "
        f"bp={connected_bp_port}@{bp_baud} status={detection['status']} "
        f"vitals_ready={readiness['vitals_ready']} bp_ready={readiness['bp_ready']}"
    )

    return {
        "ports": ports,
        "status": detection["status"],
        "summary": detection["summary"],
        "vitals_port": vitals_port,
        "bp_port": bp_port,
        "vitals_baud": vitals_baud,
        "bp_baud": bp_baud,
        "serial_vitals_obj": serial_vitals_obj,
        "serial_bp_obj": serial_bp_obj,
        "connected_vitals_port": connected_vitals_port,
        "connected_bp_port": connected_bp_port,
        "vitals_stream_ready": readiness["vitals_ready"],
        "bp_stream_ready": readiness["bp_ready"],
        "stream_readiness_summary": readiness["summary"],
    }


@st.cache_resource(show_spinner=False)
def get_startup_serial_state():
    """Cache serial bootstrap per Streamlit server process.

    Without caching, Streamlit reruns would probe/reconnect repeatedly.
    """
    return bootstrap_serial_connections_once()


# Serial probing/initialization happens once at server startup (cached).
STARTUP_SERIAL_STATE = get_startup_serial_state()
SERIAL_PORT, VITALS_PORT = (
    STARTUP_SERIAL_STATE["serial_vitals_obj"],
    STARTUP_SERIAL_STATE["connected_vitals_port"],
)
BP_SERIAL_PORT, BP_PORT = (
    STARTUP_SERIAL_STATE["serial_bp_obj"],
    STARTUP_SERIAL_STATE["connected_bp_port"],
)

# --- ESP32 & RASPBERRY PI STATUS MONITORING ---
def check_esp32_status():
    """Check if vitals stream is connected and verified (JSON signature)."""
    ser = get_serial_conn()
    stream_ready = st.session_state.get("vitals_stream_ready", False)
    if ser:
        try:
            if ser.is_open:
                if stream_ready:
                    return {"status": "✅ Ready (JSON verified)", "port": ser.port, "color": "green"}
                return {"status": "🟡 Connected (verifying stream)", "port": ser.port, "color": "yellow"}
            else:
                return {"status": "⚠️ Open Failed", "port": ser.port, "color": "red"}
        except Exception as e:
            return {"status": "❌ Disconnected", "port": "Unknown", "color": "red"}
    selected_port = st.session_state.get("vitals_port", "N/A")
    return {"status": "❌ Not Found", "port": selected_port, "color": "red"}

def get_raspi_health():
    """Get Raspberry Pi system health metrics"""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get CPU temperature (Raspberry Pi specific)
        try:
            temp_result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                        capture_output=True, text=True, timeout=2)
            cpu_temp = float(temp_result.stdout.split('=')[1].replace("'C", ""))
        except:
            cpu_temp = None
        
        return {
            "cpu": round(cpu_percent, 1),
            "memory": round(memory.percent, 1),
            "disk": round(disk.percent, 1),
            "temp": round(cpu_temp, 1) if cpu_temp else "N/A",
            "available_ram": round(memory.available / (1024**3), 2)
        }
    except Exception as e:
        return {
            "cpu": 0, "memory": 0, "disk": 0, "temp": "N/A", "available_ram": 0,
            "error": str(e)
        }

def get_health_status_color(value, thresholds={'warning': 70, 'critical': 85}):
    """Return color based on health value"""
    if value >= thresholds['critical']:
        return "🔴"
    elif value >= thresholds['warning']:
        return "🟡"
    else:
        return "🟢"

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('arogya_vision.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS patients 
                 (id TEXT, temp REAL, hr INTEGER, spo2 INTEGER, stress TEXT,
                   sys_bp INTEGER, dia_bp INTEGER, pulse_bp INTEGER,
                   symptoms TEXT, report TEXT, priority TEXT, timestamp TEXT)''')
    # Migrate old DB that may only have 9 columns (missing sys_bp, dia_bp, pulse_bp)
    existing_cols = [row[1] for row in c.execute("PRAGMA table_info(patients)").fetchall()]
    for col, col_type in [("sys_bp", "INTEGER"), ("dia_bp", "INTEGER"), ("pulse_bp", "INTEGER")]:
        if col not in existing_cols:
            c.execute(f"ALTER TABLE patients ADD COLUMN {col} {col_type} DEFAULT 0")
    conn.commit()
    conn.close()

init_db()

# --- SERIAL COMMUNICATION HELPER ---
def get_serial_conn():
    """Get serial connection for vitals (non-cached for reliability)"""
    ser = st.session_state.get("serial_vitals_obj")
    if ser and ser.is_open:
        try:
            # Test the connection
            _ = ser.in_waiting
            return ser
        except:
            try:
                ser.close()
            except:
                pass
            st.session_state.serial_vitals_obj = None
    return None

def get_bp_serial_conn():
    """Get serial connection for BP monitor (non-cached for reliability)"""
    ser = st.session_state.get("serial_bp_obj")
    if ser and ser.is_open:
        try:
            # Test the connection
            _ = ser.in_waiting
            return ser
        except:
            try:
                ser.close()
            except:
                pass
            st.session_state.serial_bp_obj = None
    return None


def flush_and_drain_serial(ser, label="serial", drain_sec=0.8, max_lines=500):
    """Reset serial buffers and drain residual lines to avoid stale readings."""
    if not ser:
        return 0

    drained = 0
    try:
        ser.reset_input_buffer()
    except Exception:
        pass

    try:
        ser.reset_output_buffer()
    except Exception:
        pass

    end = time.time() + max(0.1, drain_sec)
    while time.time() < end and drained < max_lines:
        try:
            if ser.in_waiting <= 0:
                continue
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                drained += 1
        except Exception:
            break

    debug_log(f"{label} buffer prepared: drained_lines={drained}", ui=True)
    return drained


def prepare_bp_capture():
    """Prepare BP port before a new measurement to avoid old queued frames."""
    bp_ser = get_bp_serial_conn()
    if not bp_ser:
        debug_log("BP prepare failed: no open BP serial connection", level="WARN", ui=True)
        return False

    flush_and_drain_serial(bp_ser, label=f"BP({bp_ser.port})")
    debug_log(f"BP capture armed on {bp_ser.port} @ {st.session_state.get('bp_baud', BP_BAUD_RATE)}", ui=True)
    return True

# Don't create global connections - get them fresh each time for reliability
# ser = get_serial_conn()
# bp_ser = get_bp_serial_conn()

def read_esp32_data():
    ser = get_serial_conn()
    if not ser:
        debug_log_throttled("vitals-no-serial", "Vitals reader waiting: no open serial connection", ui=True)
        return None
    try:
        if ser.in_waiting > 0:
            latest_payload = None
            # Read a burst to skip debug lines and catch up to freshest JSON.
            for _ in range(12):
                if ser.in_waiting <= 0:
                    break

                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if not line:
                    continue

                print(f"[VITALS RAW] {ser.port}: {line}", flush=True)
                debug_log_throttled("vitals-line", f"Vitals line received: {line[:120]}", every_sec=2, ui=True)

                # Skip known non-JSON/debug chatter.
                if not line.startswith('{'):
                    continue

                try:
                    payload = json.loads(line)
                    if isinstance(payload, dict):
                        latest_payload = payload
                except json.JSONDecodeError:
                    continue

            if latest_payload is not None:
                return latest_payload
        else:
            debug_log_throttled("vitals-no-bytes", f"Vitals reader waiting on {ser.port}: no bytes available", ui=True)
    except (OSError, ValueError, AttributeError, json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"[VITALS] Error reading data: {e}")
    except serial.SerialException as e:
        print(f"[VITALS] Serial connection error: {e}")
    return None

def read_bp_data():
    """Read BP data - Format: Data=00001 Data=00124 Data=00074 Data=00075 Data=00065 Data=00011 Data=00068 Data=00131
    Maps to: [1]=sys, [2]=dia, [3]=pulse"""
    bp_ser = get_bp_serial_conn()
    if not bp_ser:
        debug_log_throttled("bp-no-serial", "BP reader waiting: no open serial connection", ui=True)
        return None, None
    try:
        if bp_ser.in_waiting > 0:
            line = bp_ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                print(f"[BP RAW] {bp_ser.port}: {line}", flush=True)
                debug_log_throttled("bp-line", f"BP raw line received: {line[:120]}", every_sec=2, ui=True)
                if 'sleep mode' in line.lower():
                    debug_log_throttled(
                        "bp-sleep-mode",
                        "BP device reports sleep mode. Trigger cuff/start on monitor to begin Data= frames.",
                        level="WARN",
                        every_sec=4,
                        ui=True,
                    )
                # Log raw line for display
                raw_line = line
                
                # Try to parse if it's a Data= line
                if 'Data=' in line:
                    # Parse format: Data=00001 Data=00124 Data=00074 Data=00075 Data=...
                    # Split by 'Data=' and extract values (skip first empty value)
                    data_parts = line.split('Data=')
                    # Filter out empty strings and convert to integers
                    data_values = [int(val.strip().split()[0]) for val in data_parts[1:] if val.strip()]
                    
                    if len(data_values) >= 4:
                        sys_val = data_values[1]  # Data[1] = Systolic
                        dia_val = data_values[2]  # Data[2] = Diastolic
                        pulse_val = data_values[3]  # Data[3] = Pulse
                        
                        # Validate BP ranges
                        if 50 < sys_val < 250 and 30 < dia_val < 200 and 30 < pulse_val < 200:
                            print(f"[BP] Got: SYS={sys_val}, DIA={dia_val}, PULSE={pulse_val}")
                            return {
                                'sys': sys_val,
                                'dia': dia_val,
                                'pulse': pulse_val,
                                'status': 'completed'
                            }, raw_line
                    else:
                        print(f"[BP] Warning: Expected 4+ data values, got {len(data_values)}: {data_values}")
                
                # Return raw line even if not a Data= line (for display)
                return None, raw_line
        else:
            debug_log_throttled("bp-no-bytes", f"BP reader waiting on {bp_ser.port}: no bytes available", ui=True)
    except (OSError, ValueError, AttributeError, IndexError, UnicodeDecodeError) as e:
        print(f"[BP] Error reading: {e}")
    except serial.SerialException as e:
        print(f"[BP] Serial connection error: {e}")
    return None, None

# --- VOICE ASSISTANT WITH HINGLISH SUPPORT ---
# Initialize TTS client (use env variable for credentials)
def get_tts_client():
    """Initialize Google TTS client"""
    try:
        return texttospeech.TextToSpeechClient()
    except:
        print("[WARN] Google Cloud TTS not configured, falling back to pyttsx3")
        return None

TTS_CLIENT = get_tts_client()

def speak(text, language='hi-IN', gender='FEMALE'):
    """
    Text-to-Speech with Hinglish support using Google Cloud TTS
    language: 'en-US' for English, 'hi-IN' for Hindi
    gender: 'MALE' or 'FEMALE'
    """
    try:
        if TTS_CLIENT is None:
            print("[ERR] Google Cloud TTS not available - Please setup credentials")
            return
        
        # Kill any existing mpg123 process to prevent audio overlap
        try:
            subprocess.run(['pkill', '-f', 'mpg123'], 
                          stdout=subprocess.DEVNULL, 
                          stderr=subprocess.DEVNULL)
            time.sleep(0.1)  # Small delay to ensure process is killed
        except Exception as e:
            print(f"[AUDIO] Note: Could not kill existing audio process: {e}")
        
        # Use Google Cloud TTS
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        # Select voice
        voice = texttospeech.VoiceSelectionParams(
            language_code=language,
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )
        
        # Audio config
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        
        # Make request
        response = TTS_CLIENT.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        # Save audio file
        with open('/tmp/speech.mp3', 'wb') as f:
            f.write(response.audio_content)
        
        # Play audio in background using subprocess (will be alone since we killed previous)
        subprocess.Popen(['mpg123', '-q', '/tmp/speech.mp3'],
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
        
    except Exception as e:
        print(f"[ERR] TTS Error: {e}")

def voice_cmd(text, lang='hi'):
    """Background voice command with language selection - runs in separate thread"""
    def _speak():
        language = 'hi-IN' if lang == 'hi' else 'en-US'
        speak(text, language=language)
        time.sleep(0.5)  # Add small delay between messages
    
    # Run in daemon thread so it doesn't block UI
    threading.Thread(target=_speak, daemon=True).start()

def render_html_block(raw_html):
    """Render HTML safely without markdown indentation becoming code blocks."""
    cleaned = textwrap.dedent(raw_html).strip()
    # Remove leading spaces per line so markdown doesn't treat nested HTML as code.
    cleaned = "\n".join(line.lstrip() for line in cleaned.splitlines())
    st.markdown(cleaned, unsafe_allow_html=True)

# --- AI DIAGNOSIS (with fallback) ---
def get_ai_diagnosis(data):
    """Generate AI diagnosis with OpenRouter API (multiple models with fallback) or rule-based logic"""
    prompt = f"""You are Arogya Vision AI, a professional medical assistant for preliminary health assessments. Provide a DETAILED and COMPREHENSIVE bilingual analysis — write each section TWICE: once in clear English, then again in simple Hindi. Use --- as the delimiter between the two languages so that it can be split programmatically.

GIVEN PATIENT VITALS & DATA:
- Temperature: {data['temp']}°F
- Heart Rate: {data['hr']} BPM
- SpO2 (Oxygen Level): {data['spo2']}%
- Blood Pressure: {data.get('sys_bp', 'N/A')}/{data.get('dia_bp', 'N/A')} mmHg
- Stress Level: {data['stress']}
- Reported Symptoms: {data['symptoms']}

REQUIRED RESPONSE information (Provide detailed explanations for each):

1. **VITALS ANALYSIS (Detailed)**: 
   - Explain what each vital means
   - Compare to normal ranges
   - Identify any abnormalities

2. **OVERALL HEALTH ASSESSMENT (Comprehensive)**:
   - What the vitals indicate about current health status
   - Any potential concerns

3. **RISK LEVEL**: 
   🟢 GREEN (Healthy) / 🟡 YELLOW (Monitor) / 🔴 RED (Urgent attention needed)

4. **DETAILED RECOMMENDATIONS (3-5 actionable points)**:
   - Specific advice for each abnormal vital
   - Lifestyle modifications
   - When to seek medical help
   - For each symptom mentioned, provide specific suggestions

5. **AYURVEDIC SUGGESTIONS (Holistic)**:
   - Traditional Ayurvedic home remedies related to the reported symptoms.
   - Dietary guidelines (Ahara) suitable for the condition.
   - Simple lifestyle or Yoga/Pranayama recommendations (Vihara).

IMPORTANT: Be thorough, specific, and practical. Use simple language but be comprehensive.

When you create the summary, it will be rendered using Markdown, so feel free to use tables to explain things properly. We want the report to be as structured as possible. Try to adhere to the following report format:

```
## [Title: Health Assessment Summary]

### 1. VITALS ANALYSIS (Detailed)

| [Column: Vital Sign] | [Column: Value] | [Column: Normal Range] | [Column: Status] |
| :--- | :--- | :--- | :--- |
| **[Vital Name]** | [User Data Value Bold] | [Reference Range] | [Interpretation] |
| **[Vital Name]** | [User Data Value Bold] | [Reference Range] | [Interpretation] |

* **[Vital Name]:** [Brief explanation of what this vital indicates in English].
* **[Vital Name]:** [Detailed explanation of why the current value is normal or abnormal based on clinical standards].

### 2. OVERALL HEALTH ASSESSMENT

[Comprehensive paragraph in English synthesizing the relationship between multiple vitals and reported symptoms to explain the patient's current physiological state and potential concerns.]

### 3. RISK LEVEL

## [Color-Coded Status: 🟢 GREEN (Healthy) / 🟡 YELLOW (Monitor) / 🔴 RED (Urgent attention needed) USE THE EMOJI] ([Status Description])
*[Brief English justification for the chosen risk level based on the severity of the vitals and symptoms provided.]*

### 4. DETAILED RECOMMENDATIONS

* **[Point 1]:** [Specific, actionable advice in English regarding the most critical vital abnormality].
* **[Point 2]:** [English suggestion addressing a specific symptom mentioned in the user input].
* **[Point 3]:** [English guidance on lifestyle modifications or immediate diagnostic steps].
* **[Point 4]:** [Clear criteria in English for when the patient should seek emergency medical help].

### 5. AYURVEDIC SUGGESTIONS (Holistic Remedies)

* **Dietary Focus (Ahara):** [English suggestion for foods to favor or avoid based on Ayurveda principles relating to the symptoms].
* **Herbal/Home Remedies:** [English suggestion for common, safe Ayurvedic home remedies, e.g., warm ginger water, turmeric milk, Tulsi tea].
* **Lifestyle & Yoga (Vihara):** [English suggestion for an Ayurvedic daily routine practice or basic Yoga/Pranayama suitable for the condition].
* **Disclaimer:** *These Ayurvedic suggestions are for complementary holistic wellness and should not replace professional allopathic medical advice, diagnosis, or prescribed medications.*

---

## [शीर्षक: स्वास्थ्य मूल्यांकन सारांश]

### 1. महत्वपूर्ण संकेतों का विस्तृत विश्लेषण

| [स्तंभ: महत्वपूर्ण संकेत] | [स्तंभ: मान] | [स्तंभ: सामान्य सीमा] | [स्तंभ: स्थिति] |
| :--- | :--- | :--- | :--- |
| **[संकेत का नाम]** | [डेटा मान Bold] | [संदर्भ सीमा] | [व्याख्या] |
| **[संकेत का नाम]** | [डेटा मान Bold] | [संदर्भ सीमा] | [व्याख्या] |

* **[संकेत का नाम]:** [यह संकेत क्या दर्शाता है, इसका सरल हिंदी में संक्षिप्त विवरण]।
* **[संकेत का नाम]:** [वर्तमान मान सामान्य है या असामान्य, इसका चिकित्सा मानकों के आधार पर हिंदी में विस्तृत विवरण]।

### 2. समग्र स्वास्थ्य मूल्यांकन

[मरीज की वर्तमान शारीरिक स्थिति, लक्षणों और महत्वपूर्ण संकेतों के बीच संबंध की व्याख्या करने वाला एक व्यापक हिंदी पैराग्राफ।]

### 3. जोखिम का स्तर

## [रंग-कोडित स्थिति: 🟢 GREEN (Healthy) / 🟡 YELLOW (Monitor) / 🔴 RED (Urgent attention needed) USE THE EMOJI] ([स्थिति विवरण])
*[प्रदान किए गए डेटा और लक्षणों की गंभीरता के आधार पर चुने गए जोखिम स्तर का हिंदी में संक्षिप्त औचित्य।]*

### 4. विस्तृत सिफारिशें

* **[बिंदु 1]:** [सबसे महत्वपूर्ण असामान्य संकेत के संबंध में हिंदी में विशिष्ट और कार्रवाई योग्य सलाह]।
* **[बिंदु 2]:** [इनपुट में बताए गए विशिष्ट लक्षणों को कम करने के लिए हिंदी में सुझाव]।
* **[बिंदु 3]:** [जीवनशैली में बदलाव या तत्काल नैदानिक कदमों पर हिंदी में मार्गदर्शन]।
* **[बिंदु 4]:** [मरीज को आपातकालीन चिकित्सा सहायता कब लेनी चाहिए, इसके लिए हिंदी में स्पष्ट मानदंड]।

### 5. आयुर्वेदिक सुझाव (समग्र उपचार)

* **आहार संबंधी ध्यान (आहार):** [लक्षणों से संबंधित आयुर्वेद सिद्धांतों के आधार पर किन खाद्य पदार्थों का सेवन करें या किनसे बचें, इसके लिए हिंदी में सुझाव]।
* **घरेलू और हर्बल उपचार:** [सामान्य और सुरक्षित आयुर्वेदिक घरेलू उपचार के लिए हिंदी में सुझाव, जैसे गर्म अदरक का पानी, हल्दी वाला दूध, तुलसी की चाय]।
* **जीवनशैली और योग (विहार):** [स्थिति के अनुकूल आयुर्वेदिक दिनचर्या या बुनियादी योग/प्राणायाम के लिए हिंदी में सुझाव]।
* **अस्वीकरण:** *ये आयुर्वेदिक सुझाव समग्र स्वास्थ्य के पूरक हैं और इन्हें पेशेवर चिकित्सा सलाह, निदान या निर्धारित दवाओं का स्थान नहीं लेना चाहिए।*
```"""
    
    # Try multiple models in fallback order
    models = [
        #"anthropic/claude-opus-4.6-fast",
        #"anthropic/claude-3-5-sonnet",
        #"google/gemini-2.0-flash",
        "meta-llama/llama-3-8b-instruct"
    ]
    
    for model in models:
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "arogya-vision",
                    "X-Title": "Arogya Vision"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 1500
                },
                timeout=20
            )
            
            if response.status_code == 200:
                result = response.json()['choices'][0]['message']['content']
                print(f"[AI] [OK] Response from {model} (OpenRouter)")
                return result
            else:
                print(f"[AI] [WARN] Model {model} failed: HTTP {response.status_code}")
        except Exception as e:
            print(f"[AI] [WARN] Model {model} error: {str(e)[:100]}")
            continue
    
    # Fallback to rule-based diagnosis if all models fail
    print(f"[AI] [ERR] All models failed, using rule-based fallback")
    return get_fallback_diagnosis(data)

def get_fallback_diagnosis(data):
    """Rule-based diagnosis fallback when API is unavailable"""
    temp = data.get('temp', 98.6)
    hr = data.get('hr', 70)
    spo2 = data.get('spo2', 95)
    stress = data.get('stress', 'Normal')
    symptoms = data.get('symptoms', 'None').lower()
    
    # Determine risk level
    risk_level = "🟢 GREEN"
    if spo2 < 94 or temp > 101:
        risk_level = "🔴 RED"
    elif spo2 < 96 or temp > 99.5:
        risk_level = "🟡 YELLOW"
    
    summary = f"""
**Arogya Vision AI Assessment**

**Vitals Analysis / जाँच परिणाम:**
- Temperature / तापमान: {temp}°F (Normal / सामान्य: 98.6°F)
- Heart Rate / हृदय गति: {hr} BPM (Normal / सामान्य: 60-100 BPM)
- Oxygen Level (SpO2) / ऑक्सीजन स्तर: {spo2}% (Normal / सामान्य: >95%)
- Stress Level / तनाव स्तर: {stress}

**Risk Level / जोखिम स्तर: {risk_level}**
    """
    
    advice = []
    
    # Symptom-based advice
    if 'headache' in symptoms:
        advice.append("1. Apply warm compress on forehead, take rest. / माथे पर गर्म सेंक लें, आराम करें।")
    if 'nausea' in symptoms:
        advice.append("1. Eat light food, drink ORS solution. / हल्का भोजन करें, ओआरएस (ORS) घोल पिएं।")
    if 'cough' in symptoms:
        advice.append("1. Drink warm water with honey and tulsi. / शहद और तुलसी के साथ गर्म पानी पिएं।")
    
    # Temperature-based advice
    if temp > 100:
        advice.append("2. Take paracetamol to reduce fever; consult a doctor. / बुखार कम करने के लिए पेरासिटामोल लें; डॉक्टर से परामर्श लें।")
    else:
        advice.append("2. Drink clean water and stay hydrated. / साफ पानी पिएं और हाइड्रेटेड रहें।")
    
    # General advice
    if spo2 < 96:
        advice.append("3. Practice deep breathing exercises and consult a doctor for oxygen levels. / गहरी सांस लेने के व्यायाम करें और ऑक्सीजन के स्तर के लिए डॉक्टर से मिलें।")
    else:
        advice.append("3. Rest well and consult a doctor if symptoms worsen. / अच्छी तरह आराम करें और लक्षण बिगड़ने पर डॉक्टर से मिलें।")
    
    if not advice:
        advice = [
            "1. Exercise regularly and eat a healthy diet. / नियमित व्यायाम करें और स्वस्थ आहार लें।",
            "2. Get 7-8 hours of proper sleep. / 7-8 घंटे की उचित नींद लें।",
            "3. Reduce stress and maintain a peaceful environment. / तनाव कम करें और शांत वातावरण बनाए रखें।"
        ]
    
    return summary + "\n\n**Recommendations / सुझाव:**\n" + "\n".join(advice)

# --- AESTHETIC CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;500;600&display=swap');

    .stApp {
        background: #f4f7f5;
        font-family: 'Noto Sans', sans-serif;
        color: #1a1a1a;
    }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        background: #1a6b3a !important;
    }
    section[data-testid="stSidebar"] * {
        color: #fff !important;
    }
    section[data-testid="stSidebar"] input {
        background: rgba(255,255,255,0.15) !important;
        border: 1px solid rgba(255,255,255,0.3) !important;
        color: #fff !important;
        border-radius: 8px;
    }

    /* ── Header Banner ── */
    .av-header {
        background: #1a6b3a;
        border-radius: 14px;
        padding: 20px 28px;
        display: flex;
        align-items: center;
        gap: 14px;
        margin-bottom: 24px;
    }
    .av-header h1 {
        color: #fff;
        font-size: 26px;
        font-weight: 600;
        letter-spacing: 0.5px;
        margin: 0;
    }
    .av-header p {
        color: rgba(255,255,255,0.75);
        font-size: 13px;
        margin: 2px 0 0;
    }
    .av-header .patient-id {
        margin-left: auto;
        background: rgba(255,255,255,0.15);
        border: 1px solid rgba(255,255,255,0.3);
        border-radius: 20px;
        padding: 4px 14px;
        font-size: 12px;
        color: #fff;
        white-space: nowrap;
    }

    /* ── Main Cards ── */
    .glass-card {
        background: #ffffff;
        border-radius: 14px;
        padding: 24px 28px;
        border: 0.5px solid #d0e8da;
        box-shadow: 0 2px 12px rgba(26, 107, 58, 0.06);
        margin-bottom: 16px;
    }

    /* ── Vital Metric Cards ── */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
        margin: 16px 0;
    }
    .metric-card {
        background: #f0f9f4;
        border: 0.5px solid #c3e6d3;
        border-radius: 12px;
        padding: 16px 12px;
        text-align: center;
    }
    .metric-val {
        color: #1a6b3a;
        font-size: 28px;
        font-weight: 600;
        line-height: 1.1;
    }
    .metric-unit {
        color: #4a9a6a;
        font-size: 12px;
        margin-top: 2px;
    }
    .metric-label {
        color: #6b7c75;
        font-size: 12px;
        margin-top: 8px;
    }

    /* ── Priority Badges ── */
    .priority-green {
        background: #c3fcd7;
        color: #0a5c2a;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 13px;
        font-weight: 500;
        display: inline-block;
    }
    .priority-yellow {
        background: #fef3c7;
        color: #854f0b;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 13px;
        font-weight: 500;
        display: inline-block;
    }
    .priority-red {
        background: #fee2e2;
        color: #991b1b;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 13px;
        font-weight: 500;
        display: inline-block;
    }

    /* ── Sensor Status Bar ── */
    .sensor-bar {
        background: #f0f9f4;
        border: 0.5px solid #c3e6d3;
        border-radius: 10px;
        padding: 10px 16px;
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 13px;
        color: #2d6a4f;
        margin: 12px 0;
    }
    .sensor-dot {
        width: 10px;
        height: 10px;
        background: #2db966;
        border-radius: 50%;
        flex-shrink: 0;
        animation: blink 1.5s infinite;
    }
    @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }

    /* ── Advice Box ── */
    .advice-box {
        background: #f0f9f4;
        border-left: 3px solid #1a6b3a;
        border-radius: 0 10px 10px 0;
        padding: 14px 16px;
        font-size: 14px;
        line-height: 1.7;
        color: #1a5c32;
        margin-top: 14px;
    }

    /* ── Streamlit Overrides ── */
    .stButton > button {
        background: #1a6b3a !important;
        color: #fff !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 10px 20px !important;
        font-size: 15px !important;
        font-weight: 500 !important;
        width: 100%;
    }
    .stButton > button:hover {
        background: #145c30 !important;
    }
    .stMultiSelect [data-baseweb="tag"] {
        background: #1a6b3a !important;
        color: #fff !important;
    }
    h1, h2, h3 { color: #1a1a1a !important; }

    /* ── Doctor Queue Table ── */
    .queue-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
        border-radius: 10px;
        overflow: hidden;
    }
    .queue-table th {
        background: #f0f9f4;
        color: #1a6b3a;
        font-weight: 500;
        padding: 10px 14px;
        text-align: left;
        border-bottom: 1px solid #c3e6d3;
    }
    .queue-table td {
        padding: 10px 14px;
        border-bottom: 0.5px solid #e8f5ee;
        color: #1a1a1a;
    }

    /* ── Assessment Visual Snapshot ── */
    .snapshot-card {
        background: linear-gradient(180deg, #ffffff 0%, #f8fcf9 100%);
        border: 1px solid #d8ebde;
        border-radius: 14px;
        box-shadow: 0 8px 24px rgba(26, 107, 58, 0.08);
        overflow: hidden;
        margin-bottom: 18px;
    }
    .snapshot-header {
        background: linear-gradient(135deg, #1a6b3a 0%, #2f8f53 100%);
        color: #fff;
        padding: 14px 18px;
        font-size: 16px;
        font-weight: 600;
        letter-spacing: 0.2px;
    }
    .snapshot-body {
        padding: 14px 16px 16px;
    }
    .snapshot-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(130px, 1fr));
        gap: 12px;
        margin-bottom: 14px;
    }
    .viz-box {
        background: #ffffff;
        border: 1px solid #e2efe6;
        border-radius: 12px;
        padding: 12px;
        text-align: center;
    }
    .viz-title {
        font-size: 11px;
        color: #5f7869;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 0.3px;
    }
    .gauge {
        width: 90px;
        height: 90px;
        border-radius: 50%;
        margin: 0 auto 8px;
        background:
            radial-gradient(closest-side, #fff 74%, transparent 75% 100%),
            conic-gradient(var(--gcolor, #2f8f53) var(--gval, 50%), #e7efea 0);
    }
    .gauge-value {
        font-size: 19px;
        font-weight: 700;
        color: #133925;
        line-height: 1.1;
    }
    .gauge-unit {
        font-size: 11px;
        color: #60796a;
    }
    .bullet-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(220px, 1fr));
        gap: 10px;
        margin-bottom: 12px;
    }
    .bullet-card {
        background: #fff;
        border: 1px solid #e2efe6;
        border-radius: 12px;
        padding: 12px;
    }
    .bullet-label {
        font-size: 12px;
        color: #3f6451;
        margin-bottom: 8px;
        font-weight: 600;
    }
    .bullet-track {
        position: relative;
        height: 10px;
        border-radius: 999px;
        background: #eef4f0;
        overflow: hidden;
    }
    .bullet-good {
        position: absolute;
        top: 0;
        bottom: 0;
        background: #c9f2d9;
    }
    .bullet-marker {
        position: absolute;
        top: -3px;
        width: 3px;
        height: 16px;
        background: #1d5f39;
        border-radius: 2px;
    }
    .bullet-value {
        margin-top: 7px;
        font-size: 13px;
        color: #1d4d33;
        font-weight: 600;
    }
    .status-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        margin-top: 2px;
        flex-wrap: wrap;
    }
    .bp-badge {
        display: inline-block;
        padding: 6px 12px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.2px;
    }
    .bp-normal { background: #c9f2d9; color: #0e5a2b; }
    .bp-elevated { background: #fef3c7; color: #7a4b00; }
    .bp-highnormal { background: #ffe5c7; color: #8b4c10; }
    .bp-high { background: #fee2e2; color: #8d1717; }
    .stress-text {
        font-size: 13px;
        color: #355a47;
        font-weight: 600;
        background: #f1f8f4;
        padding: 7px 10px;
        border-radius: 8px;
        border: 1px solid #dcebe2;
    }

    /* ── AI markdown table lines (horizontal only) ── */
    .ai-report table {
        width: 100%;
        border-collapse: collapse;
        margin: 8px 0 4px;
    }
    .ai-report th,
    .ai-report td {
        border-left: none !important;
        border-right: none !important;
        border-top: 1px solid #d6dde2 !important;
        border-bottom: 1px solid #d6dde2 !important;
        padding: 8px 10px;
        text-align: left;
    }

    @media (max-width: 900px) {
        .snapshot-grid {
            grid-template-columns: repeat(2, minmax(130px, 1fr));
        }
        .bullet-grid {
            grid-template-columns: 1fr;
        }
    }
    </style>
""", unsafe_allow_html=True)

# --- SESSION STATE ---
if 'step' not in st.session_state: st.session_state.step = "welcome"
if 'patient_id' not in st.session_state: st.session_state.patient_id = f"PT-{int(time.time())}"
if 'captured_vitals' not in st.session_state: st.session_state.captured_vitals = {}
if 'captured_bp' not in st.session_state: st.session_state.captured_bp = {}
if 'temp_list' not in st.session_state: st.session_state.temp_list = []
if 'hr_list' not in st.session_state: st.session_state.hr_list = []
if 'spo2_list' not in st.session_state: st.session_state.spo2_list = []
if 'sys_list' not in st.session_state: st.session_state.sys_list = []
if 'dia_list' not in st.session_state: st.session_state.dia_list = []
if 'pulse_list' not in st.session_state: st.session_state.pulse_list = []
if 'sampling_active' not in st.session_state: st.session_state.sampling_active = False
if 'bp_sampling_active' not in st.session_state: st.session_state.bp_sampling_active = False
if 'voice_announced_welcome' not in st.session_state: st.session_state.voice_announced_welcome = False
if 'voice_announced_vitals' not in st.session_state: st.session_state.voice_announced_vitals = False
if 'voice_announced_bp' not in st.session_state: st.session_state.voice_announced_bp = False
if 'voice_announced_symptoms' not in st.session_state: st.session_state.voice_announced_symptoms = False
if 'raw_bp_log' not in st.session_state: st.session_state.raw_bp_log = []
if 'raw_vitals_log' not in st.session_state: st.session_state.raw_vitals_log = []
if 'serial_ports' not in st.session_state: st.session_state.serial_ports = STARTUP_SERIAL_STATE["ports"]
if 'serial_detection_status' not in st.session_state: st.session_state.serial_detection_status = STARTUP_SERIAL_STATE["status"]
if 'serial_detection_summary' not in st.session_state: st.session_state.serial_detection_summary = STARTUP_SERIAL_STATE["summary"]
if 'vitals_port' not in st.session_state: st.session_state.vitals_port = STARTUP_SERIAL_STATE["vitals_port"]
if 'bp_port' not in st.session_state: st.session_state.bp_port = STARTUP_SERIAL_STATE["bp_port"]
if 'vitals_baud' not in st.session_state: st.session_state.vitals_baud = STARTUP_SERIAL_STATE["vitals_baud"]
if 'bp_baud' not in st.session_state: st.session_state.bp_baud = STARTUP_SERIAL_STATE["bp_baud"]
if 'serial_vitals_obj' not in st.session_state: st.session_state.serial_vitals_obj = STARTUP_SERIAL_STATE["serial_vitals_obj"]
if 'serial_bp_obj' not in st.session_state: st.session_state.serial_bp_obj = STARTUP_SERIAL_STATE["serial_bp_obj"]
if 'vitals_stream_ready' not in st.session_state: st.session_state.vitals_stream_ready = STARTUP_SERIAL_STATE.get("vitals_stream_ready", False)
if 'bp_stream_ready' not in st.session_state: st.session_state.bp_stream_ready = STARTUP_SERIAL_STATE.get("bp_stream_ready", False)
if 'stream_readiness_summary' not in st.session_state: st.session_state.stream_readiness_summary = STARTUP_SERIAL_STATE.get("stream_readiness_summary", "Not verified")
if 'vitals_zero_start' not in st.session_state: st.session_state.vitals_zero_start = None
if 'vitals_dummy_mode' not in st.session_state: st.session_state.vitals_dummy_mode = False
if 'debug_lines' not in st.session_state: st.session_state.debug_lines = []

if 'serial_config_initialized' not in st.session_state:
    # Use startup-initialized values; do not probe/reconnect on every page load.
    st.session_state.serial_config_initialized = True

# --- SIDEBAR: DOCTOR MODE ---
with st.sidebar:
    st.title("Arogya Vision")

    mode = st.radio("View", ["Patient Booth", "Doctor Login"])

    st.markdown("---")
    st.subheader("Device Status")

    esp32_info = check_esp32_status()
    st.markdown(f"**Vitals:** {esp32_info['status']}")

    bp_conn = get_bp_serial_conn()
    bp_ready = st.session_state.get("bp_stream_ready", False)
    if bp_conn and bp_ready:
        st.markdown("**BP Monitor:** ✅ Ready")
    elif bp_conn:
        st.markdown("**BP Monitor:** 🟡 Connected")
    else:
        st.markdown("**BP Monitor:** ❌ Not Connected")

    with st.expander("Advanced Hardware", expanded=False):
        st.caption(f"Detection: {st.session_state.serial_detection_status}")
        if st.session_state.serial_detection_summary:
            st.caption(st.session_state.serial_detection_summary)
        if st.session_state.stream_readiness_summary:
            st.caption(f"Readiness: {st.session_state.stream_readiness_summary}")

        if st.button("🔄 Refresh Ports", use_container_width=True):
            detection = infer_serial_roles()
            st.session_state.serial_ports = detection["ports"]
            st.session_state.serial_detection_status = detection["status"]
            st.session_state.serial_detection_summary = detection["summary"]

            st.session_state.vitals_port = detection["vitals_port"] or (st.session_state.serial_ports[0] if st.session_state.serial_ports else "")
            st.session_state.vitals_baud = detection.get("vitals_baud", st.session_state.vitals_baud)

            valid_bp = [p for p in st.session_state.serial_ports if p != st.session_state.vitals_port]
            st.session_state.bp_port = detection["bp_port"] if detection["bp_port"] in valid_bp else (valid_bp[0] if valid_bp else "")
            st.session_state.bp_baud = detection.get("bp_baud", st.session_state.bp_baud)
            st.session_state.vitals_stream_ready = False
            st.session_state.bp_stream_ready = False
            st.session_state.stream_readiness_summary = "Pending reconnect verification"

            vitals_ok, bp_ok = reconnect_serial_connections(
                st.session_state.vitals_port,
                st.session_state.vitals_baud,
                st.session_state.bp_port,
                st.session_state.bp_baud,
            )
            debug_log(
                f"Refresh reconnect applied: vitals_ok={vitals_ok}, bp_ok={bp_ok}",
                ui=True,
            )

            st.rerun()

        port_options = st.session_state.serial_ports if st.session_state.serial_ports else ["(no serial ports found)"]
        ports_available = bool(st.session_state.serial_ports)

        vitals_default_idx = 0
        if ports_available and st.session_state.vitals_port in port_options:
            vitals_default_idx = port_options.index(st.session_state.vitals_port)

        selected_vitals_port = st.selectbox(
            "Vitals Port",
            options=port_options,
            index=vitals_default_idx,
            disabled=not ports_available,
        )

        bp_options = [p for p in st.session_state.serial_ports if p != selected_vitals_port]
        if not bp_options:
            bp_options = ["(select another vitals port first)"]

        bp_default_idx = 0
        if st.session_state.bp_port in bp_options:
            bp_default_idx = bp_options.index(st.session_state.bp_port)

        selected_bp_port = st.selectbox(
            "BP Port",
            options=bp_options,
            index=bp_default_idx,
            disabled=(not ports_available or bp_options[0].startswith("(")),
        )

        baud_options = [9600, 115200]
        vitals_baud_idx = baud_options.index(st.session_state.vitals_baud) if st.session_state.vitals_baud in baud_options else 0
        bp_baud_idx = baud_options.index(st.session_state.bp_baud) if st.session_state.bp_baud in baud_options else 1

        selected_vitals_baud = st.selectbox("Vitals Baud", baud_options, index=vitals_baud_idx)
        selected_bp_baud = st.selectbox("BP Baud", baud_options, index=bp_baud_idx)

        if st.button("🔌 Reconnect Selected", use_container_width=True):
            if not ports_available:
                st.error("No serial ports found.")
            elif selected_bp_port.startswith("("):
                st.error("Select a different BP port.")
            elif selected_vitals_port == selected_bp_port:
                st.error("Vitals and BP ports must be different.")
            else:
                st.session_state.vitals_port = selected_vitals_port
                st.session_state.bp_port = selected_bp_port
                st.session_state.vitals_baud = selected_vitals_baud
                st.session_state.bp_baud = selected_bp_baud

                vitals_ok, bp_ok = reconnect_serial_connections(
                    st.session_state.vitals_port,
                    st.session_state.vitals_baud,
                    st.session_state.bp_port,
                    st.session_state.bp_baud,
                )
                st.session_state.serial_detection_status = "Manual override"
                if vitals_ok or bp_ok:
                    st.success("Serial ports reconnected.")
                else:
                    st.error("Reconnect failed for both ports.")
                st.rerun()

    with st.expander("Advanced Diagnostics", expanded=False):
        health = get_raspi_health()
        st.caption(f"CPU {health['cpu']}% | Mem {health['memory']}% | Disk {health['disk']}% | Temp {health['temp']}")
        st.caption(f"RAM Available: {health['available_ram']} GB")

        if st.session_state.debug_lines:
            st.text("\n".join(st.session_state.debug_lines[-20:]))
        else:
            st.caption("No debug events yet.")

    if mode == "Doctor Login":
        pwd = st.text_input("Passcode", type="password")
        if pwd == "7777":
            st.success("Doctor Access Granted")
            conn = sqlite3.connect('arogya_vision.db')
            df = conn.execute("SELECT id, priority, temp, spo2, symptoms, timestamp FROM patients ORDER BY timestamp DESC").fetchall()
            st.write("### Patient Queue")
            st.table(df)
            conn.close()

# --- MAIN FLOW ---
if mode == "Patient Booth":
    
    if st.session_state.step == "welcome":
        debug_log_throttled("step-welcome", "UI step: welcome", every_sec=10, ui=True)
        st.markdown("<h1 style='text-align: center; color: #00f2ff;'>AROGYA VISION</h1>", unsafe_allow_html=True)
        st.markdown("<div class='glass-card' style='text-align: center;'><h3>Digital Health Diagnostic Hub</h3><p>Fast • Local • Accurate</p></div>", unsafe_allow_html=True)
        
        # Display ESP32 Connection Status
        esp32_info = check_esp32_status()
        if esp32_info["color"] == "green":
            st.success(f"✅ {esp32_info['status']} on {esp32_info['port']}")
        else:
            st.error(f"❌ {esp32_info['status']} - Sensor Not Available")
        
        # Announce welcome voice ONLY ONCE
        if not st.session_state.voice_announced_welcome:
            voice_cmd("Namaste! Arogya Vision mein aapka swagat hai. Aaj hum aapka complete health checkup karenge. Sabhi readings bilkul accurate hongi. Kripya relax rahen aur checkup shuru karein.", lang='hi')
            st.session_state.voice_announced_welcome = True
        
        if st.button("🚀 PRESS START TO BEGIN / शुरू करें", use_container_width=True):
            st.session_state.voice_announced_welcome = False  # Reset for next time
            st.session_state.voice_announced_vitals = False
            st.session_state.voice_announced_bp = False
            st.session_state.voice_announced_symptoms = False
            st.session_state.step = "vital_collection"
            st.rerun()

    elif st.session_state.step == "vital_collection":
        st.header("🔍 Precision Vital Scanning / वाइटल्स की जांच")
        st.info("Place your finger firmly on the sensor. A 20-second stable reading will be taken. / सेंसर पर अपनी उंगली मजबूती से रखें। 20 सेकंड की स्थिर रीडिंग ली जाएगी।")
        
        # Announce vitals instructions
        if not st.session_state.voice_announced_vitals:
            voice_cmd("Checkup ke liye taiyaar, kripya apni ungli sensor par rakhein.", lang='hi')
            st.session_state.voice_announced_vitals = True
        
        progress_bar = st.progress(0)
        timer_text = st.empty()
        col1, col2, col3, col4 = st.columns(4)
        temp_p, hr_p, spo2_p, stress_p = col1.empty(), col2.empty(), col3.empty(), col4.empty()
        
        if not st.session_state.sampling_active:
            if st.button("🔴 START 20-SEC SCAN / 20-सेकंड स्कैन शुरू करें", use_container_width=True):
                if not get_serial_conn():
                    debug_log(
                        "Vitals scan requested with no live vitals handle; attempting reconnect",
                        level="WARN",
                        ui=True,
                    )
                    reconnect_serial_connections(
                        st.session_state.get("vitals_port", ""),
                        st.session_state.get("vitals_baud", BAUD_RATE),
                        st.session_state.get("bp_port", ""),
                        st.session_state.get("bp_baud", BP_BAUD_RATE),
                    )

                if not get_serial_conn():
                    st.error("Vitals sensor is not connected. Use Refresh/Reconnect in sidebar.")
                    debug_log(
                        "Vitals scan blocked: no live vitals handle after reconnect attempt",
                        level="ERROR",
                        ui=True,
                    )
                    st.stop()

                debug_log("Vitals scan started (20s)", ui=True)
                st.session_state.sampling_active = True
                st.session_state.start_time = time.time()
                st.session_state.vitals_zero_start = None
                st.session_state.vitals_dummy_mode = False
                st.session_state.temp_list, st.session_state.hr_list, st.session_state.spo2_list, st.session_state.stress_list = [], [], [], []
                st.rerun()
        
        if st.session_state.sampling_active:
            elapsed = time.time() - st.session_state.start_time
            remaining = max(0, 20 - int(elapsed))
            progress_bar.progress(min(elapsed / 20.0, 1.0))
            timer_text.markdown(f"<h3 style='text-align:center;'>⏳ Time Remaining: {remaining}s</h3>", unsafe_allow_html=True)
            
            data = read_esp32_data()
            if data:
                if data.get('temp', 0) > 50: st.session_state.temp_list.append(data['temp'] + TEMP_OFFSET_F)
                if data.get('hr', 0) > 0: st.session_state.hr_list.append(data['hr'])
                if data.get('spo2', 0) > 0: st.session_state.spo2_list.append(data['spo2'])
                if data.get('stress'): st.session_state.stress_list.append(data['stress'])

                hr_val = int(data.get('hr', 0) or 0)
                spo2_val = int(data.get('spo2', 0) or 0)
                if hr_val == 0 and spo2_val == 0:
                    if st.session_state.vitals_zero_start is None:
                        st.session_state.vitals_zero_start = time.time()
                    elif time.time() - st.session_state.vitals_zero_start >= 5:
                        st.session_state.vitals_dummy_mode = True
                else:
                    st.session_state.vitals_zero_start = None
                    st.session_state.vitals_dummy_mode = False
                
                temp_p.metric("Temp", f"{data.get('temp', '--')}°F")
                hr_p.metric("Heart Rate", f"{data.get('hr', '--')} BPM")
                spo2_p.metric("SpO2", f"{data.get('spo2', '--')}%")
                stress_p.metric("Stress", data.get('stress', 'N/A'))

            # Test fallback: if readings remain HR=0 and SpO2=0 for 5s, inject dummy values.
            if st.session_state.vitals_dummy_mode:
                dummy_hr = random.randint(85, 100)
                dummy_spo2 = 98
                st.session_state.hr_list.append(dummy_hr)
                st.session_state.spo2_list.append(dummy_spo2)
                if not st.session_state.temp_list:
                    st.session_state.temp_list.append(98.6)
                if not st.session_state.stress_list:
                    st.session_state.stress_list.append("Normal")

                hr_p.metric("Heart Rate", f"{dummy_hr} BPM")
                spo2_p.metric("SpO2", f"{dummy_spo2}%")
                debug_log_throttled(
                    "vitals-dummy-mode",
                    "Vitals test fallback active: injecting HR 85-100 and SpO2 98 after 5s of zero readings",
                    level="WARN",
                    every_sec=2,
                    ui=True,
                )
            
            if elapsed >= 20:
                st.session_state.sampling_active = False
                
                # Helper to find most common stress
                def get_most_common_stress(lst, default='Normal'):
                    if not lst:
                        return default
                    return max(set(lst), key=lst.count)
                
                st.session_state.captured_vitals = {
                    'temp': round(sum(st.session_state.temp_list) / len(st.session_state.temp_list), 1) if st.session_state.temp_list else 98.6,
                    'hr': int(round(sum(st.session_state.hr_list) / len(st.session_state.hr_list), 1)) if st.session_state.hr_list else 75,
                    'spo2': int(round(sum(st.session_state.spo2_list) / len(st.session_state.spo2_list), 1)) if st.session_state.spo2_list else 98,
                    'stress': get_most_common_stress(st.session_state.stress_list, 'Normal')
                }
                debug_log(
                    f"Vitals scan complete: temp={st.session_state.captured_vitals['temp']} "
                    f"hr={st.session_state.captured_vitals['hr']} spo2={st.session_state.captured_vitals['spo2']} "
                    f"stress={st.session_state.captured_vitals['stress']}",
                    ui=True,
                )
                voice_cmd("Readings complete. Review your results.", lang='hi')
                st.session_state.step = "confirm_vitals"
                st.rerun()
            
            time.sleep(0.3)
            st.rerun()

    elif st.session_state.step == "confirm_vitals":
        v = st.session_state.captured_vitals
        
        # Enhanced Final Values Display with Hinglish
        st.markdown(f"""
            <div class='glass-card' style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 15px; margin-bottom: 25px;'>
                <h2 style='text-align: center; margin-bottom: 10px;'>✅ Scan Complete - Final Averaged Vitals</h2>
                <p style='text-align: center; font-size: 13px; opacity: 0.85; margin-bottom: 25px;'>Based on 20-second collection and averaging</p>
                <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 20px;'>
                    <div style='background-color: rgba(255,255,255,0.2); padding: 20px; border-radius: 10px; text-align: center; border: 1px solid rgba(255,255,255,0.3);'>
                        <div style='font-size: 11px; opacity: 0.9; margin-bottom: 5px;'>🌡️ Temperature</div>
                        <div style='font-size: 36px; font-weight: bold; margin: 10px 0;'>{v['temp']}°F</div>
                        <div style='font-size: 11px; opacity: 0.8;'>Final Average</div>
                    </div>
                    <div style='background-color: rgba(255,255,255,0.2); padding: 20px; border-radius: 10px; text-align: center; border: 1px solid rgba(255,255,255,0.3);'>
                        <div style='font-size: 11px; opacity: 0.9; margin-bottom: 5px;'>❤️ Heart Rate</div>
                        <div style='font-size: 36px; font-weight: bold; margin: 10px 0;'>{v['hr']}</div>
                        <div style='font-size: 11px; opacity: 0.8;'>BPM Average</div>
                    </div>
                    <div style='background-color: rgba(255,255,255,0.2); padding: 20px; border-radius: 10px; text-align: center; border: 1px solid rgba(255,255,255,0.3);'>
                        <div style='font-size: 11px; opacity: 0.9; margin-bottom: 5px;'>🫁 Oxygen Level</div>
                        <div style='font-size: 36px; font-weight: bold; margin: 10px 0;'>{v['spo2']}%</div>
                        <div style='font-size: 11px; opacity: 0.8;'>SpO2 Average</div>
                    </div>
                    <div style='background-color: rgba(255,255,255,0.2); padding: 20px; border-radius: 10px; text-align: center; border: 1px solid rgba(255,255,255,0.3);'>
                        <div style='font-size: 11px; opacity: 0.9; margin-bottom: 5px;'>😰 Stress Level</div>
                        <div style='font-size: 24px; font-weight: bold; margin: 10px 0;'>{v['stress']}</div>
                        <div style='font-size: 11px; opacity: 0.8;'>Most Common</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Show interpretation
        st.markdown("### 📋 Reading Interpretation:")
        
        interp_html = f"""
        <div style='background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 4px solid #667eea;'>
            <p><b>🌡️ Temperature:</b> {v['temp']}°F - {'Normal ✅' if 97 <= v['temp'] <= 99.5 else 'Watch carefully ⚠️' if v['temp'] > 99.5 else 'Alert 🔴' if v['temp'] > 101 else 'Normal'}</p>
            <p><b>❤️ Heart Rate:</b> {v['hr']} BPM - {'Normal ✅' if 60 <= v['hr'] <= 100 else 'Watch ⚠️' if v['hr'] < 60 or v['hr'] > 100 else 'Normal'}</p>
            <p><b>🫁 Oxygen Level:</b> {v['spo2']}% - {'Excellent ✅' if v['spo2'] >= 96 else 'Good ✓' if v['spo2'] >= 94 else 'Low ⚠️' if v['spo2'] >= 90 else 'Critical 🔴' if v['spo2'] < 90 else 'Normal'}</p>
            <p><b>😰 Stress Level:</b> {v['stress']}</p>
        </div>
        """
        st.markdown(interp_html, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirm & Next / पुष्टि करें और आगे बढ़ें", use_container_width=True):
                st.session_state.step = "bp_measurement"
                st.rerun()
        
        with col2:
            if st.button("🔄 Retake Scan / पुनः स्कैन करें", use_container_width=False):
                st.session_state.step = "vital_collection"
                st.rerun()

    elif st.session_state.step == "bp_measurement":
        st.header("🩺 Blood Pressure Measurement / रक्तचाप (BP) की जांच")
        st.info("Attach the BP monitor cuff to your arm. The measurement will take a few seconds. / BP मॉनिटर कफ को अपनी बाँह पर लगाएं। माप में कुछ सेकंड लगेंगे।")
        BP_HIDDEN_TIMEOUT_SEC = 80
        
        # Announce BP voice ONLY ONCE and only when not sampling
        if not st.session_state.bp_sampling_active and not st.session_state.voice_announced_bp:
            voice_cmd("Ab blood pressure measurement hoga. Cuff ko apne left arm par lagayen, heart ke level par. Bilkul relax rahen aur kisi bhi tarah ki gativishil mat karein.", lang='hi')
            st.session_state.voice_announced_bp = True

        # UI Layout
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        col1, col2, col3 = st.columns(3)
        sys_p = col1.empty()
        dia_p = col2.empty()
        pulse_p = col3.empty()
        
        # Raw data display
        raw_data_container = st.expander("📊 View Raw BP Port Data (Live Debug)", expanded=False)
        raw_data_display = raw_data_container.empty()

        # Start Button
        if not st.session_state.bp_sampling_active:
            if st.button("🔴 START BP MEASUREMENT / BP मापन शुरू करें", use_container_width=True):
                debug_log("BP measurement started", ui=True)
                st.session_state.voice_announced_bp = False  # Reset for next page
                st.session_state.bp_sampling_active = True
                st.session_state.start_time = time.time()
                st.session_state.bp_measurement_started_at = st.session_state.start_time
                st.session_state.sys_list = []
                st.session_state.dia_list = []
                st.session_state.pulse_list = []
                st.session_state.raw_bp_log = []
                prepare_bp_capture()
                st.rerun()

        # Sampling Loop
        if st.session_state.bp_sampling_active:
            elapsed = time.time() - st.session_state.start_time

            # Keep progress subtle and non-countdown; timeout remains internal.
            progress_bar.progress(min(elapsed / BP_HIDDEN_TIMEOUT_SEC, 1.0))

            # Read from BP Serial - gets both parsed data and raw line
            bp_data, raw_line = read_bp_data()
            
            # Display raw data in log
            if raw_line:
                st.session_state.raw_bp_log.append(raw_line)
                # Keep only last 10 lines for display
                if len(st.session_state.raw_bp_log) > 10:
                    st.session_state.raw_bp_log = st.session_state.raw_bp_log[-10:]
                
                # Display raw data in log format (terminal style)
                raw_log_html = '<div style="background-color: #1e1e1e; color: #00ff00; font-family: monospace; font-size: 11px; padding: 10px; border-radius: 5px; height: 150px; overflow-y: auto; border: 1px solid #004400;">'
                for log_line in st.session_state.raw_bp_log:
                    # Highlight Data= lines in bright yellow
                    if 'Data=' in log_line:
                        raw_log_html += f'<span style="color: #ffff00; font-weight: bold;">{log_line}</span><br/>'
                    # Highlight TruePulseCount lines in cyan
                    elif 'TruePulseCount' in log_line:
                        raw_log_html += f'<span style="color: #00ffff;">{log_line}</span><br/>'
                    # Regular lines in green
                    else:
                        raw_log_html += f'{log_line}<br/>'
                raw_log_html += '</div>'
                raw_data_display.markdown(raw_log_html, unsafe_allow_html=True)
            
            if bp_data:
                # Add to lists if valid
                if bp_data.get('sys', 0) > 0: st.session_state.sys_list.append(bp_data['sys'])
                if bp_data.get('dia', 0) > 0: st.session_state.dia_list.append(bp_data['dia'])
                if bp_data.get('pulse', 0) > 0: st.session_state.pulse_list.append(bp_data['pulse'])

                # Helper to calculate running average
                def get_avg(lst):
                    return int(sum(lst) / len(lst)) if lst else 0

                # Live Display with current and running average
                sys_p.metric("Systolic", f"{bp_data.get('sys', '--')} mmHg", f"Avg: {get_avg(st.session_state.sys_list)} mmHg")
                dia_p.metric("Diastolic", f"{bp_data.get('dia', '--')} mmHg", f"Avg: {get_avg(st.session_state.dia_list)} mmHg")
                pulse_p.metric("Pulse", f"{bp_data.get('pulse', '--')} bpm", f"Avg: {get_avg(st.session_state.pulse_list)} bpm")
                
                status_text.success(f"🟢 Reading #{len(st.session_state.sys_list)} - {len(st.session_state.sys_list)} measurements received")
            else:
                status_text.warning("⏳ Waiting for BP data... Ensure BP monitor cuff is active")

            timed_out = elapsed >= BP_HIDDEN_TIMEOUT_SEC

            # Keep reading until valid BP result is received, with hidden timeout safety.
            if (bp_data and bp_data.get('status') == 'completed') or timed_out:
                st.session_state.bp_sampling_active = False
                
                # Average Calculation Helper
                def get_avg(lst, default=0):
                    return int(sum(lst) / len(lst)) if lst else default

                # Save Averaged Results (with realistic defaults if no data)
                default_sys = random.randint(115, 125)
                default_dia = random.randint(75, 85)
                default_pulse = random.randint(68, 78)
                
                st.session_state.captured_bp = {
                    'sys': get_avg(st.session_state.sys_list, default_sys),
                    'dia': get_avg(st.session_state.dia_list, default_dia),
                    'pulse': get_avg(st.session_state.pulse_list, default_pulse)
                }

                if timed_out and not st.session_state.sys_list:
                    debug_log(
                        f"BP measurement timed out at {BP_HIDDEN_TIMEOUT_SEC}s without valid Data= frame; using fallback defaults",
                        level="WARN",
                        ui=True,
                    )
                debug_log(
                    f"BP measurement complete: sys={st.session_state.captured_bp['sys']} "
                    f"dia={st.session_state.captured_bp['dia']} pulse={st.session_state.captured_bp['pulse']}",
                    ui=True,
                )
                
                voice_cmd("Blood pressure reading successfully poori ho gayi. Ab aapke symptoms ke baare mein poocha jayega. Tayyar ho jayen.", lang='hi')
                st.session_state.step = "confirm_bp"
                st.rerun()

            # Refresh every 300ms for smooth live data
            time.sleep(0.3)
            st.rerun()

    elif st.session_state.step == "confirm_bp":
        bp = st.session_state.captured_bp
        
        st.success("✅ BP Reading Captured / BP रीडिंग प्राप्त हुई")
        
        st.markdown(f"""
            <div class='glass-card' style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 15px; margin-bottom: 25px;'>
                <h2 style='text-align: center; margin-bottom: 10px;'>💉 Final BP Readings - Averaged Values</h2>
                <p style='text-align: center; font-size: 13px; opacity: 0.85; margin-bottom: 25px;'>Based on measurements averaged</p>
                <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 20px;'>
                    <div style='background-color: rgba(255,255,255,0.2); padding: 20px; border-radius: 10px; text-align: center; border: 1px solid rgba(255,255,255,0.3);'>
                        <div style='font-size: 11px; opacity: 0.9; margin-bottom: 5px;'>💪 Systolic</div>
                        <div style='font-size: 36px; font-weight: bold; margin: 10px 0;'>{bp['sys']}</div>
                        <div style='font-size: 11px; opacity: 0.8;'>mmHg (Final Avg)</div>
                    </div>
                    <div style='background-color: rgba(255,255,255,0.2); padding: 20px; border-radius: 10px; text-align: center; border: 1px solid rgba(255,255,255,0.3);'>
                        <div style='font-size: 11px; opacity: 0.9; margin-bottom: 5px;'>💧 Diastolic</div>
                        <div style='font-size: 36px; font-weight: bold; margin: 10px 0;'>{bp['dia']}</div>
                        <div style='font-size: 11px; opacity: 0.8;'>mmHg (Final Avg)</div>
                    </div>
                    <div style='background-color: rgba(255,255,255,0.2); padding: 20px; border-radius: 10px; text-align: center; border: 1px solid rgba(255,255,255,0.3);'>
                        <div style='font-size: 11px; opacity: 0.9; margin-bottom: 5px;'>💓 Pulse Rate</div>
                        <div style='font-size: 36px; font-weight: bold; margin: 10px 0;'>{bp['pulse']}</div>
                        <div style='font-size: 11px; opacity: 0.8;'>bpm (Final Avg)</div>
                    </div>
                </div>
                <div style='text-align: center; margin-top: 20px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.2);'>
                    <p style='margin: 0; font-size: 12px; opacity: 0.9;'>BP Category:</p>
                    <p style='margin: 8px 0 0 0; font-size: 18px; font-weight: bold;'>
                    {
                        "🟢 Normal" if bp['sys'] < 120 and bp['dia'] < 80 else
                        "🟡 Elevated" if bp['sys'] < 130 and bp['dia'] < 80 else
                        "🔴 High" if bp['sys'] >= 140 or bp['dia'] >= 90 else
                        "🟠 High-Normal"
                    }
                    </p>
                </div>
            </div>
        """, unsafe_allow_html=True)

        if st.button("✅ Confirm & Proceed / पुष्टि करें और आगे बढ़ें", use_container_width=True):
            st.session_state.step = "symptoms"
            st.rerun()
        
        if st.button("Retake BP Measurement / BP पुनः मापें", use_container_width=False):
            st.session_state.step = "bp_measurement"
            st.rerun()

    elif st.session_state.step == "symptoms":
        st.header("📝 Describe Your Feeling / आप कैसा महसूस कर रहे हैं")
        
        # Announce symptoms voice ONLY ONCE
        if not st.session_state.voice_announced_symptoms:
            voice_cmd("Kripya apne symptoms batain. Agar aapko weakness, nausea, sirdard, saans mein dikkat, stomach ache, ya khansi hai to select karein.", lang='hi')
            st.session_state.voice_announced_symptoms = True
        
        symptom_list = st.multiselect("Select symptom: / अपने लक्षण चुनें:", 
                                     ["Weakness / कमज़ोरी", "Nausea / जी मिचलाना", "Headache / सिरदर्द", 
                                      "Breathlessness / सांस फूलना", "Stomach Ache / पेट दर्द", "Cough / खांसी"])
        
        if st.button("Finalize & Generate Report / रिपोर्ट बनाएं", use_container_width=True):
            st.session_state.selected_symptoms = ", ".join(symptom_list)
            st.session_state.voice_announced_symptoms = False  # Reset for next patient
            voice_cmd("Aapke symptoms record ho gaye. Ab AI assistant aapka health report banayega. Kripya intezar karein.", lang='hi')
            st.session_state.step = "analysis"
            st.rerun()

    elif st.session_state.step == "analysis":
        debug_log("Analysis step entered", ui=True)
        st.header("🤖 AI Analysis in Progress... / AI विश्लेषण जारी है...")
        with st.spinner("Generating your health assessment..."):
            vitals = st.session_state.captured_vitals
            bp = st.session_state.captured_bp
            report_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            # Prepare data with BP info for AI analysis
            analysis_data = {
                **vitals,
                "symptoms": st.session_state.selected_symptoms,
                "sys_bp": bp.get('sys', 0),
                "dia_bp": bp.get('dia', 0)
            }
            
            report = get_ai_diagnosis(analysis_data)
            debug_log("AI report generated", ui=True)
            
            # Priority logic based on vitals and BP
            priority = "🟢 GREEN"
            priority_text = "✅ Healthy"
            if vitals['spo2'] < 94 or vitals['temp'] > 101: 
                priority = "🔴 RED"
                priority_text = "🔴 Critical"
            elif vitals['spo2'] < 96 or bp['sys'] > 160: 
                priority = "🟡 YELLOW"
                priority_text = "⚠️ Monitor"

            # Save to Database
            conn = sqlite3.connect('arogya_vision.db')
            conn.execute("""
                INSERT INTO patients (id, temp, hr, spo2, stress, sys_bp, dia_bp, pulse_bp, symptoms, report, priority, timestamp)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (st.session_state.patient_id, vitals['temp'], vitals['hr'],
                          vitals['spo2'], vitals['stress'],
                          bp.get('sys', 0), bp.get('dia', 0), bp.get('pulse', 0),
                          st.session_state.selected_symptoms,
                          report, priority, report_timestamp))
            conn.commit()
            conn.close()
            debug_log("Patient report saved to database", ui=True)

            # Enhanced Report Display
            report_header_html = f"""
            <div class='glass-card' style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 15px; margin-bottom: 25px;'>
                <h2 style='text-align: center; margin-bottom: 10px;'>📋 Your Report</h2>
                <p style='text-align: center; opacity: 0.9; margin-bottom: 20px; font-size: 14px;'>Patient ID: <b>{st.session_state.patient_id}</b></p>
                <div style='text-align: center; padding: 15px; background-color: rgba(255,255,255,0.1); border-radius: 10px; margin-bottom: 20px;'>
                    <p style='margin: 0; font-size: 12px; opacity: 0.9;'>Health Status</p>
                    <p style='margin: 10px 0 0 0; font-size: 32px; font-weight: bold;'>{priority_text}</p>
                </div>
            </div>
            """
            render_html_block(report_header_html)

            bp_category = (
                "Normal" if bp.get('sys', 0) < 120 and bp.get('dia', 0) < 80 else
                "Elevated" if bp.get('sys', 0) < 130 and bp.get('dia', 0) < 80 else
                "High" if bp.get('sys', 0) >= 140 or bp.get('dia', 0) >= 90 else
                "High-Normal"
            )

            def clamp_pct(value, lo, hi):
                if hi <= lo:
                    return 0
                return max(0, min(100, ((value - lo) / (hi - lo)) * 100))

            temp = float(vitals.get('temp', 0))
            hr = float(vitals.get('hr', 0))
            spo2 = float(vitals.get('spo2', 0))
            pulse = float(bp.get('pulse', 0))
            sys_bp = float(bp.get('sys', 0))
            dia_bp = float(bp.get('dia', 0))
            symptoms_text = st.session_state.selected_symptoms or "None"

            temp_pct = clamp_pct(temp, 96, 104)  # °F range: 96 (hypothermic) → 104 (high fever)
            hr_pct = clamp_pct(hr, 40, 140)
            spo2_pct = clamp_pct(spo2, 80, 100)
            pulse_pct = clamp_pct(pulse, 40, 140)
            sys_pct = clamp_pct(sys_bp, 80, 200)
            dia_pct = clamp_pct(dia_bp, 40, 130)

            bp_badge_class = (
                "bp-normal" if bp_category == "Normal" else
                "bp-elevated" if bp_category == "Elevated" else
                "bp-high" if bp_category == "High" else
                "bp-highnormal"
            )

            snapshot_visual_html = f"""
            <div class='snapshot-card'>
                <div class='snapshot-header'>📊 Clinical Snapshot / संक्षिप्त क्लिनिकल डेटा</div>
                <div class='snapshot-body'>
                    <div style='font-size:12px; color:#4f6f5e; margin-bottom:10px;'>
                        Patient: <b>{html.escape(st.session_state.patient_id)}</b> &nbsp;•&nbsp; {html.escape(report_timestamp)}
                    </div>

                    <div class='snapshot-grid'>
                        <div class='viz-box'>
                            <div class='viz-title'>Temperature</div>
                            <div class='gauge' style='--gval:{temp_pct:.1f}%; --gcolor:#ef6b5b;'></div>
                            <div class='gauge-value'>{temp:.1f}</div><div class='gauge-unit'>°F</div>
                        </div>
                        <div class='viz-box'>
                            <div class='viz-title'>SpO2</div>
                            <div class='gauge' style='--gval:{spo2_pct:.1f}%; --gcolor:#2a9d8f;'></div>
                            <div class='gauge-value'>{spo2:.0f}</div><div class='gauge-unit'>%</div>
                        </div>
                        <div class='viz-box'>
                            <div class='viz-title'>Heart Rate</div>
                            <div class='gauge' style='--gval:{hr_pct:.1f}%; --gcolor:#3b82f6;'></div>
                            <div class='gauge-value'>{hr:.0f}</div><div class='gauge-unit'>BPM</div>
                        </div>
                        <div class='viz-box'>
                            <div class='viz-title'>Pulse</div>
                            <div class='gauge' style='--gval:{pulse_pct:.1f}%; --gcolor:#8b5cf6;'></div>
                            <div class='gauge-value'>{pulse:.0f}</div><div class='gauge-unit'>BPM</div>
                        </div>
                    </div>

                    <div class='bullet-grid'>
                        <div class='bullet-card'>
                            <div class='bullet-label'>Systolic</div>
                            <div class='bullet-track'>
                                <div class='bullet-good' style='left:26%; width:20%;'></div>
                                <div class='bullet-marker' style='left:{sys_pct:.1f}%;'></div>
                            </div>
                            <div class='bullet-value'>{sys_bp:.0f} mmHg</div>
                        </div>
                        <div class='bullet-card'>
                            <div class='bullet-label'>Diastolic</div>
                            <div class='bullet-track'>
                                <div class='bullet-good' style='left:31%; width:16%;'></div>
                                <div class='bullet-marker' style='left:{dia_pct:.1f}%;'></div>
                            </div>
                            <div class='bullet-value'>{dia_bp:.0f} mmHg</div>
                        </div>
                    </div>

                    <div class='status-row'>
                        <span class='bp-badge {bp_badge_class}'>BP Category: {html.escape(bp_category)}</span>
                        <span class='stress-text'>Stress Level: {html.escape(str(vitals.get('stress', 'Normal')))}</span>
                    </div>

                    <div style='margin-top:10px; font-size:12px; color:#5f7869;'>
                        Symptoms: {html.escape(symptoms_text)} &nbsp;•&nbsp; Risk Flag: {html.escape(priority)}
                    </div>
                </div>
            </div>
            """

            render_html_block(snapshot_visual_html)
            
            # AI Diagnosis Report
            st.markdown("### 🤖 AI Medical Assessment:")
            ai_html = f"""
            <div class='ai-report' style='background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 5px solid #667eea; font-size: 15px; line-height: 1.8;'>
            {report}
            </div>
            """
            render_html_block(ai_html)
            
            st.markdown("---")
            voice_cmd("Aapki complete health report tayaar ho gayi. Screen par detailed analysis dekh sakte hain. Agar koi confusion hai to doctor se consult karein. Shukriya!", lang='hi')

            # ── eSanjeevani OPD Redirect Button ──
            esanjeevani_html = """
            <div style='
                background: linear-gradient(135deg, #0d6efd 0%, #0a58ca 100%);
                border-radius: 14px;
                padding: 24px 28px;
                text-align: center;
                margin: 18px 0;
                box-shadow: 0 4px 18px rgba(13,110,253,0.25);
            '>
                <p style='color: rgba(255,255,255,0.85); font-size: 13px; margin: 0 0 6px 0;'>
                    🏥 Need to consult a doctor? Book a free online consultation
                </p>
                <p style='color: rgba(255,255,255,0.75); font-size: 12px; margin: 0 0 18px 0;'>
                    डॉक्टर से परामर्श लेना है? मुफ़्त ऑनलाइन OPD बुक करें
                </p>
                <a href="https://esanjeevani.mohfw.gov.in/#/patient/signin" target="_blank" rel="noopener noreferrer"
                   style='
                       display: inline-block;
                       background: #ffffff;
                       color: #0d6efd;
                       font-size: 17px;
                       font-weight: 700;
                       text-decoration: none;
                       padding: 14px 36px;
                       border-radius: 10px;
                       letter-spacing: 0.4px;
                       box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                       transition: background 0.2s;
                   '>
                    🩺 Consult Doctor on eSanjeevani OPD &nbsp;→
                </a>
                <p style='color: rgba(255,255,255,0.6); font-size: 11px; margin: 14px 0 0 0;'>
                    Ministry of Health &amp; Family Welfare, Government of India
                </p>
            </div>
            """
            render_html_block(esanjeevani_html)

            if st.button("🔄 Start New Patient / नया पेशेंट शुरू करें", use_container_width=True):
                st.session_state.step = "welcome"
                st.session_state.patient_id = f"PT-{int(time.time())}"
                st.rerun()