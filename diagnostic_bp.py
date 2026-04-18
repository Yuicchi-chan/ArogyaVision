#!/usr/bin/env python3
"""
🔧 BP Monitor Diagnostic Tool
Helps identify why BP data isn't being received
"""

import serial
import time
import re
import glob

BP_BAUD_RATE = 115200
VITALS_BAUD = 9600

def colorize(text, color):
    colors = {
        'green': '\033[92m',
        'red': '\033[91m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'reset': '\033[0m'
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"


def test_port(port, baud_rate, duration=5):
    """Test a specific port and show what data it sends"""
    print(f"\n{colorize('='*60, 'blue')}")
    print(f"Testing {colorize(port, 'yellow')} at {colorize(str(baud_rate), 'yellow')} baud")
    print(f"{colorize('='*60, 'blue')}")
    
    try:
        ser = serial.Serial(port, baud_rate, timeout=1)
        time.sleep(0.5)
        
        print(f"✓ Port opened successfully")
        print(f"Listening for {duration} seconds...\n")
        
        deadline = time.time() + duration
        line_count = 0
        data_found = False
        data_types = {'json': 0, 'data_format': 0, 'other': 0}
        
        while time.time() < deadline:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    line_count += 1
                    data_found = True
                    
                    # Categorize data
                    if line.startswith('{') or '"' in line:
                        data_types['json'] += 1
                        print(f"  [{line_count}] JSON: {line[:80]}")
                    elif 'Data=' in line:
                        data_types['data_format'] += 1
                        # Parse Data= format
                        matches = re.findall(r'Data=(\d+)', line)
                        if matches:
                            print(f"  [{line_count}] Data Format ({len(matches)} values): {', '.join(matches)}")
                        else:
                            print(f"  [{line_count}] Data Format (unparseable): {line[:80]}")
                    else:
                        data_types['other'] += 1
                        print(f"  [{line_count}] Other: {line[:80]}")
        
        ser.close()
        
        if data_found:
            print(f"\n✓ Data received!")
            print(f"  - JSON format: {data_types['json']} lines")
            print(f"  - Data= format: {data_types['data_format']} lines")
            print(f"  - Other format: {data_types['other']} lines")
        else:
            print(f"\n⚠ No data received on this port")
        
        return data_found
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main():
    print(f"\n{colorize('🔧 BP MONITOR DIAGNOSTIC TOOL', 'blue')}\n")
    
    ports = sorted(glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*'))
    
    if not ports:
        print(colorize("❌ No serial ports found!", 'red'))
        return
    
    print(f"Found {len(ports)} serial port(s):\n")
    for p in ports:
        print(f"  - {p}")
    
    print(f"\n{colorize('Testing each port...', 'yellow')}\n")
    
    results = {}
    
    # Test vitals baud rate (9600)
    print(f"\n{colorize('Phase 1: Testing at 9600 baud (Vitals)', 'cyan')}")
    for port in ports:
        found = test_port(port, VITALS_BAUD, duration=3)
        results[port] = {'9600': found}
    
    # Test BP baud rate (115200)
    print(f"\n\n{colorize('Phase 2: Testing at 115200 baud (BP Monitor)', 'cyan')}")
    for port in ports:
        found = test_port(port, BP_BAUD_RATE, duration=3)
        if port not in results:
            results[port] = {}
        results[port]['115200'] = found
    
    # Summary
    print(f"\n\n{colorize('='*60, 'blue')}")
    print(colorize('📊 SUMMARY', 'blue'))
    print(f"{colorize('='*60, 'blue')}\n")
    
    vitals_port = None
    bp_port = None
    
    for port, baudrates in results.items():
        if baudrates.get('9600'):
            vitals_port = port
            print(colorize(f"✓ Vitals found on {port} (9600 baud)", 'green'))
        
        if baudrates.get('115200'):
            bp_port = port
            print(colorize(f"✓ BP Monitor found on {port} (115200 baud)", 'green'))
    
    print()
    
    if not vitals_port:
        print(colorize("⚠ Vitals sensor not detected on any port!", 'red'))
    
    if not bp_port:
        print(colorize("❌ BP Monitor not detected on any port!", 'red'))
        print("\nTroubleshooting:")
        print("1. Check USB cables are connected")
        print("2. Ensure BP device is powered on")
        print("3. Try plugging into different USB ports")
        print("4. Check device firmware is loaded")
    else:
        print(colorize("✓ BP Monitor is connected and transmitting!", 'green'))
    
    print(f"\n{colorize('For app configuration:', 'yellow')}")
    print(f"  VITALS_PORT: {vitals_port or 'NOT FOUND'}")
    print(f"  BP_PORT: {bp_port or 'NOT FOUND'}")
    
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{colorize('Test cancelled by user', 'yellow')}")
    except Exception as e:
        print(f"\n{colorize(f'Error: {e}', 'red')}")
