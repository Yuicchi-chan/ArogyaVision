#!/usr/bin/env python3
"""Test BP data parser with actual format from device"""

def parse_bp_data(line):
    """Parse BP format: Data=00128 Data=00074 Data=00104 Data=00065 ..."""
    if line and 'Data=' in line:
        import re
        # Extract all numeric values after "Data="
        matches = re.findall(r'Data=(\d+)', line)
        data_values = [int(m) for m in matches]
        
        # Data format: [status, SYS, DIA, PULSE, ...]
        if len(data_values) >= 4:
            sys_val = data_values[1]
            dia_val = data_values[2]
            pulse_val = data_values[3]
            
            # Validate BP ranges
            if 0 < sys_val < 250 and 0 < dia_val < 200 and 0 < pulse_val < 180:
                return {
                    'sys': sys_val,
                    'dia': dia_val,
                    'pulse': pulse_val,
                    'status': 'completed'
                }
    return None

# Test with actual data from your device
test_data = [
    "Data=00001 Data=00128 Data=00074 Data=00104 Data=00065 Data=00011 Data=00059 Data=00135",
    "Data=00001 Data=00120 Data=00080 Data=00070 Data=00100 Data=00050",
    "Data=00001 Data=00140 Data=00090 Data=00075 Data=00120 Data=00060",
]

print("🧪 Testing BP Data Parser\n")
print("=" * 60)

for i, line in enumerate(test_data, 1):
    result = parse_bp_data(line)
    print(f"\n📝 Test {i}:")
    print(f"   Input:  {line}")
    if result:
        print(f"   ✅ Parsed: SYS={result['sys']} DIA={result['dia']} PULSE={result['pulse']}")
    else:
        print(f"   ❌ Failed to parse")

print("\n" + "=" * 60)
print("\n✓ Parser ready to use in app.py")
