import requests
import json
import sys
import os
from dotenv import load_dotenv

# Load API key from environment or use hardcoded
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")

# Free models to try (in order of preference)
FREE_MODELS = [
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "mistralai/mistral-7b-instruct:free",
    "meta-llama/llama-2-7b-chat:free",
    "gryphe/mythomax-l2-13b:free"
]

def test_api_key_validity():
    """Verify API key is valid"""
    print("\n🔑 Testing API Key Validity...")
    try:
        response = requests.get(
            url="https://openrouter.ai/api/v1/auth/key",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API Key Valid!")
            print(f"   Credits Used: ${data.get('usage', 'N/A')}")
            return True
        else:
            print(f"❌ Invalid API Key: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def test_free_models():
    """Test which free models are available and working"""
    print("\n🔍 Testing Free Models...")
    working_models = []
    
    for model in FREE_MODELS:
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "max_tokens": 10,
                    "temperature": 0.7
                },
                timeout=15
            )
            
            if response.status_code == 200:
                print(f"   ✅ {model}")
                working_models.append(model)
            elif response.status_code == 404:
                print(f"   ⚠️  {model} - Not available")
            elif response.status_code == 402:
                print(f"   ⚠️  {model} - No credits")
            else:
                print(f"   ❌ {model} ({response.status_code})")
        except requests.exceptions.Timeout:
            print(f"   ⏱️  {model} - Timeout")
        except Exception as e:
            print(f"   ❌ {model} - {str(e)[:30]}")
    
    return working_models

def test_diagnosis_with_model(model_id):
    """Test the full AI diagnosis with a specific model"""
    print(f"\n{'='*60}")
    print(f"🤖 Testing Full AI Diagnosis")
    print(f"Model: {model_id}")
    print(f"{'='*60}")
    
    test_data = {
        "temp": 99.5,
        "hr": 85,
        "spo2": 97,
        "stress": "Normal",
        "symptoms": "Mild headache"
    }
    
    prompt = f"""You are Arogya Vision AI, a medical assistant. 
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
3. 3 Practical Advice points (Hinglish)"""
    
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 500
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                diagnosis = result['choices'][0]['message']['content']
                print("\n✅ Diagnosis Generated Successfully!\n")
                print(diagnosis)
                return True
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text[:300]}")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def main():
    print("=" * 60)
    print("AROGYA VISION - API KEY TEST SUITE")
    print("=" * 60)
    
    # Test API key
    if not test_api_key_validity():
        print("\n❌ API key is invalid. Please check your credentials.")
        return
    
    # Test free models
    working_models = test_free_models()
    
    if not working_models:
        print("\n❌ No working free models found.")
        print("   - Check your API key has free tier access")
        print("   - Check your internet connection")
        return
    
    # Test diagnosis with first working model
    best_model = working_models[0]
    test_diagnosis_with_model(best_model)
    
    print(f"\n{'='*60}")
    print(f"✅ All tests completed!")
    print(f"{'='*60}")
    print(f"\n📝 RECOMMENDATION:")
    print(f"Update app.py to use: {best_model}")

if __name__ == "__main__":
    main()
