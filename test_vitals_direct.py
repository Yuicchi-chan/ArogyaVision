#!/usr/bin/env python3
"""
Quick test to verify Vitals Sensor connection and data
Run: python3 test_vitals_direct.py
"""

import serial
import json
import time

VITALS_PORT = "/dev/vitals_sensor"
VITALS_BAUD = 9600

def test_vitals():
    print(f"Testing Vitals Sensor at {VITALS_PORT} ({VITALS_BAUD} baud)")
    print("=" * 60)
    
    try:
        # Open connection
        ser = serial.Serial(VITALS_PORT, VITALS_BAUD, timeout=1)
        time.sleep(0.5)
        ser.reset_input_buffer()
        print(f"✓ Connected to {VITALS_PORT}")
        print()
        print("⏳ Waiting for finger on sensor (looking for 'touch':true)...")
        print("=" * 60)
        
        # Read until we get valid readings (touch=true)
        valid_count = 0
        total_count = 0
        temp_list = []
        hr_list = []
        spo2_list = []
        
        while valid_count < 10 and total_count < 100:  # Stop after 10 valid or 100 total lines
            try:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    total_count += 1
                    
                    if line:
                        # Try to parse as JSON
                        try:
                            data = json.loads(line)
                            
                            # Check if touch sensor detected
                            touch = data.get('touch', False)
                            
                            if touch:
                                # Valid reading - finger on sensor
                                temp = data.get('temp', 'N/A')
                                hr = data.get('hr', 'N/A')
                                spo2 = data.get('spo2', 'N/A')
                                stress = data.get('stress', 'N/A')
                                
                                # Add to lists for averaging
                                if isinstance(temp, (int, float)) and temp > 50:
                                    temp_list.append(temp)
                                if isinstance(hr, int) and 40 < hr < 200:
                                    hr_list.append(hr)
                                if isinstance(spo2, int) and spo2 > 0:
                                    spo2_list.append(spo2)
                                
                                valid_count += 1
                                print(f"[{valid_count}] ✓ VALID (touch:true) - Temp: {temp}°F | HR: {hr} BPM | SpO2: {spo2}% | Stress: {stress}")
                            else:
                                # Invalid - no finger on sensor
                                print(f"[{total_count}] ✗ Invalid (touch:false) - Waiting for finger...")
                        except json.JSONDecodeError:
                            # Show raw line if can't parse
                            print(f"[{total_count}] ⚠ Raw: {line[:60]}")
                else:
                    time.sleep(0.1)
            
            except Exception as e:
                print(f"Error: {e}")
        
        print("=" * 60)
        
        if valid_count > 0:
            avg_temp = round(sum(temp_list) / len(temp_list), 1) if temp_list else 0
            avg_hr = round(sum(hr_list) / len(hr_list), 1) if hr_list else 0
            avg_spo2 = round(sum(spo2_list) / len(spo2_list), 1) if spo2_list else 0
            
            print(f"\n✓ Results: {valid_count}/10 VALID readings collected")
            print(f"\n📊 AVERAGED VALUES (based on {valid_count} valid readings):")
            print(f"   🌡️  Temperature Average: {avg_temp}°F")
            print(f"   ❤️  Heart Rate Average: {int(avg_hr)} BPM")
            print(f"   🫁 SpO2 Average: {int(avg_spo2)}%")
            print()
            
            if valid_count >= 5:
                print("✅ Vitals sensor is working correctly!")
                print("   Keep your finger steady on the sensor for best results.")
            else:
                print("⚠️  Only a few valid readings - make sure finger stays on sensor")
        else:
            print(f"\n❌ No valid readings obtained (tried {total_count} lines)")
            print("Troubleshooting:")
            print("   1. Check if sensor is connected")
            print("   2. Make sure your finger is on the sensor")
            print("   3. Check that /dev/vitals_sensor exists: ls -la /dev/vitals_sensor")
        
        ser.close()
        
    except FileNotFoundError:
        print(f"✗ ERROR: Device not found at {VITALS_PORT}")
        print("Make sure udev rule is set up:")
        print("  sudo ls -la /dev/vitals_sensor")
    except serial.SerialException as e:
        print(f"✗ Serial error: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")

if __name__ == "__main__":
    test_vitals()

