#!/bin/bash
cd /home/pi/Desktop/New/ArogyaVision

# Kill old processes
pkill -f streamlit

# Start streamlit in the BACKGROUND (the '&' is very important!)
source env/bin/activate
streamlit run app.py --server.port 8502 --server.headless true &

# Wait for the server to wake up
sleep 8

# Force the browser to open on the Pi's monitor
export DISPLAY=:0
chromium-browser --app=http://localhost:8502
