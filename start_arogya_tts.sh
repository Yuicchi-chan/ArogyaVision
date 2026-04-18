#!/bin/bash

# Arogya Vision Startup Script with Google Cloud TTS

echo "🚀 Starting Arogya Vision with Google Cloud TTS..."
echo ""

# Set Google Cloud Credentials
export GOOGLE_APPLICATION_CREDENTIALS="/home/pi/Desktop/New/ArogyaVision/asv-tech-e61349084e55.json"

# Verify credentials
if [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "✅ Google Cloud Credentials Found"
else
    echo "❌ Credentials file not found!"
    exit 1
fi

# Verify environment variable
if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "❌ Environment variable not set!"
    exit 1
fi

echo "✅ Google Cloud TTS: ACTIVE"
echo "✅ Female Voice: ENABLED"
echo "✅ Language: Hinglish (Hindi + English)"
echo ""
echo "🎙️  Your app will now use professional female voice!"
echo ""

# Start Streamlit app
cd /home/pi/Desktop/New/ArogyaVision
streamlit run app.py --logger.level=error

