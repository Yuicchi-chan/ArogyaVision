#!/usr/bin/env python3
"""
Test script to verify BP ESP32 connection and data format
Run this to diagnose BP communication issues
"""

import serial
import json
import glob
import time

def find_serial_ports():
    """Find all available serial ports"""
    import sys
    if sys.platform.startswith('win'):
        import serial.tools.list_ports
        return [port.device for port in serial.tools.list_ports.comports()]
    ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
    return sorted(ports)

def test_bp_port(port, baud_rate=115200, timeout=5):
    """Test a specific port for BP monitor data"""
    print(f"\n{'='*60}")
    print(f"Testing port: {port} at {baud_rate} baud")
    print(f"{'='*60}")
    
    try:
        ser = serial.Serial(port, baud_rate, timeout=1)
        print(f"✅ Port opened successfully")
        
        print(f"Listening for data for {timeout} seconds...\n")
        start_time = time.time()
        data_count = 0
        valid_json_count = 0
        
        while time.time() - start_time < timeout:
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('utf-8').strip()
                    if line:
                        data_count += 1
                        print(f"[Raw] {line}")
                        
                        # Try to parse as JSON
                        try:
                            data = json.loads(line)
                            valid_json_count += 1
                            
                            # Validate BP data
                            if 'sys' in data and 'dia' in data and 'pulse' in data:
                                sys_val = data['sys']
                                dia_val = data['dia']
                                pulse_val = data['pulse']
                                status = data.get('status', 'unknown')
                                
                                # Check if values are reasonable
                                if 0 < sys_val < 250 and 0 < dia_val < 200 and 0 < pulse_val < 180:
                                    print(f"✅ [Valid BP Data] SYS:{sys_val} DIA:{dia_val} PULSE:{pulse_val} STATUS:{status}")
                                else:
                                    print(f"⚠️  [Out of range] SYS:{sys_val} DIA:{dia_val} PULSE:{pulse_val}")
                            else:
                                print(f"⚠️  [Missing fields] {data}")
                        
                        except json.JSONDecodeError as e:
                            print(f"❌ [Not JSON] Error: {e}")
                
                except UnicodeDecodeError as e:
                    print(f"❌ [Decode error] {e}")
            
            time.sleep(0.1)
        
        ser.close()
        
        print(f"\n{'='*60}")
        print(f"Results for {port}:")
        print(f"  Lines received: {data_count}")
        print(f"  Valid JSON lines: {valid_json_count}")
        if data_count == 0:
            print(f"  ❌ NO DATA RECEIVED - Check BP monitor connection!")
        print(f"{'='*60}\n")
        
        return data_count > 0
        
    except serial.SerialException as e:
        print(f"❌ Cannot open port: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("BP ESP32 Connection Tester")
    print("="*60)
    
    ports = find_serial_ports()
    
    if not ports:
        print("❌ No serial ports found!")
        print("   Please check USB connections:")
        print("   - Vitals ESP32 (9600 baud)")
        print("   - BP Monitor ESP32 (115200 baud)")
        return
    
    print(f"\n📍 Found {len(ports)} serial port(s): {ports}")
    
    # Test each port at both baud rates
    for port in ports:
        print(f"\n🔍 Testing {port}...")
        
        # Try BP baud rate (115200)
        if test_bp_port(port, baud_rate=115200, timeout=5):
            print(f"✅ {port} appears to be the BP monitor!")
            break
        
        # Try standard baud rate (9600) 
        print(f"\nAlso trying {port} at 9600 baud...")
        test_bp_port(port, baud_rate=9600, timeout=3)

if __name__ == "__main__":
    main()
