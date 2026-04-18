#!/usr/bin/env python3
"""Test BP detection and data reading from actual serial port"""

import serial
import re
import time
import glob

BP_BAUD_RATE = 115200

def parse_bp_data(line):
    """Parse BP format: Data=00128 Data=00074 Data=00104 ..."""
    if line and 'Data=' in line:
        matches = re.findall(r'Data=(\d+)', line)
        data_values = [int(m) for m in matches]
        
        if len(data_values) >= 4:
            sys_val = data_values[1]
            dia_val = data_values[2]
            pulse_val = data_values[3]
            
            if 0 < sys_val < 250 and 0 < dia_val < 200 and 0 < pulse_val < 180:
                return {
                    'sys': sys_val,
                    'dia': dia_val,
                    'pulse': pulse_val
                }
    return None

print("🔍 Testing BP Data from Serial Port\n")

# Try each port
ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
print(f"Found ports: {ports}\n")

for port in ports:
    print(f"Testing {port} at {BP_BAUD_RATE} baud...")
    try:
        ser = serial.Serial(port, BP_BAUD_RATE, timeout=2)
        time.sleep(0.5)
        
        # Read for 5 seconds
        deadline = time.time() + 30
        bp_found = False
        
        while time.time() < deadline:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if 'Data=' in line:
                    bp_data = parse_bp_data(line)
                    if bp_data:
                        print(f"✅ {port}: SYS={bp_data['sys']} DIA={bp_data['dia']} PULSE={bp_data['pulse']}")
                        bp_found = True
                        break
        
        if not bp_found:
            print(f"⏳ {port}: No BP data found (waiting...)\n")
        
        ser.close()
    except Exception as e:
        print(f"❌ {port}: {str(e)}\n")

print("\n✓ Test complete!")
