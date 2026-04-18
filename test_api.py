import requests
import json
import sys

# Test OpenRouter API Key
OPENROUTER_API_KEY = "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"

def test_api_key_format():
    """Test if API key has the correct format"""
    print("🔍 Testing API Key Format...")
    if OPENROUTER_API_KEY.startswith("sk-or-v1-"):
        print("✅ API Key format is valid (OpenRouter format detected)")
        return True
    else:
        print("❌ API Key format is invalid")
        return False

def test_api_connectivity():
    """Test if OpenRouter API is accessible"""
    print("\n🔗 Testing API Connectivity...")
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "meta-llama/llama-3-8b-instruct:free",
                "messages": [{"role": "user", "content": "Say 'test successful' in one word"}],
                "max_tokens": 10
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ API is accessible (Status: 200)")
            return True
        elif response.status_code == 401:
            print("❌ Unauthorized - API Key is invalid or expired")
            print(f"Response: {response.text}")
            return False
        else:
            print(f"⚠️  Unexpected status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except requests.exceptions.Timeout:
        print("❌ Request timeout - API server not responding")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - Check internet connection")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def test_ai_diagnosis_function():
    """Test the actual AI diagnosis function from app"""
    print("\n🤖 Testing AI Diagnosis Function...")
    test_data = {
        "temp": 99.5,
        "hr": 85,
        "spo2": 97,
        "stress": "Normal",
        "symptoms": "Mild headache"
    }
    
    prompt = f"""
    You are Arogya Vision AI, a medical assistant. 
    Analyze these vitals and symptoms for a primary assessment in Hinglish (Hindi + English).
    
    PATIENT DATA:
    - Temperature: {test_data['temp']} F
    - Heart Rate: {test_data['hr']} BPM
    - SpO2: {test_data['spo2']} %
    - Stress Level: {test_data['stress']}
    - Symptoms: {test_data['symptoms']}
    
    FORMAT:
    1. Summary (Short explanation in Hinglish)
    2. Risk Level (Green/Yellow/Red)
    3. 3 Practical Advice points (Hinglish)
    """
    
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            json={
                "model": "meta-llama/llama-3-8b-instruct:free",
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                diagnosis = result['choices'][0]['message']['content']
                print("✅ AI Diagnosis function works")
                print(f"\nDiagnosis Output:\n{diagnosis}")
                return True
            else:
                print("❌ Unexpected response format")
                print(f"Response: {result}")
                return False
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def run_all_tests():
    """Run all tests"""
    print("=" * 50)
    print("AROGYA VISION - API KEY TEST SUITE")
    print("=" * 50)
    
    results = {
        "Format Test": test_api_key_format(),
        "Connectivity Test": test_api_connectivity(),
        "AI Diagnosis Test": test_ai_diagnosis_function()
    }
    
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    print("=" * 50)
    if all_passed:
        print("✅ ALL TESTS PASSED - API is working!")
    else:
        print("❌ SOME TESTS FAILED - Check configuration")
    print("=" * 50)
    
    return all_passed

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
