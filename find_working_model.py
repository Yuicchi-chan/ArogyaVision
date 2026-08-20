import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()
OPENROUTER_API_KEY = "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"

# Models to try in order (prioritized by cost/quality)
MODELS_TO_TRY = [
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-3-27b-it:free",
    "mistralai/mistral-7b-instruct:free",
    "meta-llama/llama-2-7b-chat:free",
    "openai-community/gpt2",
    "anthropic/claude-3-5-sonnet",
    "google/gemini-2.0-flash",
    "qwen/qwen-7b-chat",
]

def test_model(model_id):
    """Test if a model works"""
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "Arogya Vision"
            },
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 10,
                "temperature": 0.7
            },
            timeout=15
        )

        status = response.status_code
        if status == 200:
            return True, "✅ WORKS"
        elif status == 402:
            return False, "❌ Insufficient credits"
        elif status == 404:
            return False, "⚠️  Model not found"
        elif status == 429:
            return False, "⏱️  Rate limited"
        else:
            return False, f"Error {status}"
    except requests.exceptions.Timeout:
        return False, "⏱️  Timeout"
    except Exception as e:
        return False, f"Error: {str(e)[:30]}"

print("=" * 70)
print("FINDING WORKING MODELS FOR YOUR API KEY")
print("=" * 70)

working_models = []
for model in MODELS_TO_TRY:
    success, msg = test_model(model)
    status = "✅" if success else "❌"
    print(f"{status} {model:<50} {msg}")
    if success:
        working_models.append(model)

print("\n" + "=" * 70)
if working_models:
    print(f"✅ WORKING MODELS FOUND: {len(working_models)}")
    print("=" * 70)
    for i, model in enumerate(working_models, 1):
        print(f"{i}. {model}")
    
    print(f"\n📝 RECOMMENDED: Use '{working_models[0]}' in app.py")
else:
    print("❌ NO WORKING MODELS FOUND")
    print("=" * 70)
    print("Solution: Your API key may not have credits for any paid models.")
    print("Try one of these:")
    print("  1. Create a new OpenRouter account (includes free credits)")
    print("  2. Add payment method to your account")
    print("  3. Use a different API service (HuggingFace, DeepSeek, etc.)")
