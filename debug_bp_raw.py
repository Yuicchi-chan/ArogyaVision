#!/usr/bin/env python3
"""
Detailed BP data debug - shows raw output from BP ESP32
"""

import serial
import time

def debug_bp_port(port='/dev/ttyUSB0', baud_rate=115200, timeout=10):
    """Show raw data from BP monitor"""
    print(f"\n{'='*70}")
    print(f"BP Monitor Debug - Raw Data Capture")
    print(f"{'='*70}")
    print(f"Port: {port}")
    print(f"Baud Rate: {baud_rate}")
    print(f"Timeout: {timeout}s")
    print(f"{'='*70}\n")
    
    try:
        ser = serial.Serial(port, baud_rate, timeout=1)
        print("✅ Port opened. Capturing data...\n")
        
        start_time = time.time()
        line_count = 0
        
        while time.time() - start_time < timeout:
            if ser.in_waiting > 0:
                try:
                    # Read raw bytes
                    data = ser.read(ser.in_waiting)
                    
                    # Show hex representation
                    hex_str = ' '.join(f'{b:02x}' for b in data)
                    
                    # Try to decode as string
                    try:
                        text_str = data.decode('utf-8')
                        printable = ''.join(c if c.isprintable() or c in '\n\r' else f'[0x{ord(c):02x}]' for c in text_str)
                    except:
                        text_str = "[Binary data]"
                        printable = text_str
                    
                    line_count += 1
                    print(f"[Line {line_count}] HEX:  {hex_str}")
                    print(f"[Line {line_count}] TEXT: {printable}")
                    print()
                    
                except Exception as e:
                    print(f"❌ Error: {e}\n")
            
            time.sleep(0.05)
        
        ser.close()
        
        if line_count == 0:
            print("❌ NO DATA RECEIVED")
            print("\nTroubleshooting:")
            print("1. Check BP ESP32 is powered on")
            print("2. Verify USB cable is connected")
            print("3. Try: lsusb  (to see if device is detected)")
            print("4. Try: dmesg | tail  (to see USB events)")
        else:
            print(f"\n✅ Received {line_count} lines of data")
            print("\nAnalysis:")
            print("- If you see JSON like {\"sys\":..., \"dia\":..., \"pulse\":...}")
            print("  → Data format is correct! ✅")
            print("- If you see other text (like 'Data=', 'Sys[0]=', etc.)")
            print("  → Arduino code needs update to JSON format")
        
    except serial.SerialException as e:
        print(f"❌ Cannot open port: {e}")

if __name__ == "__main__":
    try:
        debug_bp_port(port='/dev/ttyUSB0', baud_rate=115200, timeout=10)
    except KeyboardInterrupt:
        print("\n\n⏹ Stopped by user")
