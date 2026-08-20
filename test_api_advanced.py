import requests
import json
import sys
import os
from dotenv import load_dotenv

# Load API key from environment or use hardcoded (not recommended for production)
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")

def test_list_available_models():
    """List all available models on OpenRouter"""
    print("📊 Fetching Available Models...")
    try:
        response = requests.get(
            url="https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            models = data.get('data', [])
            if models:
                print(f"✅ Found {len(models)} available models\n")
                print("Top Free/Recommended Models:")
                for i, model in enumerate(models[:10]):
                    print(f"  {i+1}. {model['id']}")
                return True, models
            else:
                print("❌ No models found")
                return False, []
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
            return False, []
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False, []

def test_with_specific_model(model_id, test_prompt="Say 'test successful'"):
    """Test API with a specific model"""
    print(f"\n🧪 Testing with Model: {model_id}...")
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": test_prompt}],
                "max_tokens": 50,
                "temperature": 0.7
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
                print(f"✅ Success!")
                print(f"   Response: {content[:100]}...")
                return True
            else:
                print(f"⚠️  Unexpected format: {result}")
                return False
        else:
            print(f"❌ Error ({response.status_code}): {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def test_ai_diagnosis_with_working_model(model_id):
    """Test the full AI diagnosis with a working model"""
    print(f"\n🤖 Testing Full AI Diagnosis with {model_id}...")
    
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
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result:
                diagnosis = result['choices'][0]['message']['content']
                print("✅ Full Diagnosis Works!\n")
                print("=" * 50)
                print(diagnosis)
                print("=" * 50)
                return True
        else:
            print(f"❌ Error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def run_full_test():
    """Run comprehensive test"""
    print("=" * 60)
    print("AROGYA VISION - ADVANCED API TEST")
    print("=" * 60)
    
    # Test 1: List models
    success, models = test_list_available_models()
    
    if not success or not models:
        print("\n⚠️  Could not retrieve models. Check your API key and internet connection.")
        return
    
    # Test 2: Try first available model
    first_model = models[0]['id']
    print(f"\n{'=' * 60}")
    print(f"Testing with first available model: {first_model}")
    print(f"{'=' * 60}")
    
    if test_with_specific_model(first_model):
        # Test 3: Run full diagnosis
        test_ai_diagnosis_with_working_model(first_model)
    
    print(f"\n{'=' * 60}")
    print("✅ Test Complete!")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    run_full_test()
