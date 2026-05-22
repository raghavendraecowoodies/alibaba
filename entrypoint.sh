#!/bin/bash

# Exit immediately if any command fails
set -e

echo "Starting X Virtual Framebuffer (Xvfb) on display :99..."
# Start Xvfb in the background, suppressing logs
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp > /dev/null 2>&1 &

# Store PID of Xvfb to kill it gracefully later
XVFB_PID=$!

# Export the DISPLAY environment variable so Chrome knows where to render
export DISPLAY=:99
export DOCKER_ENV=true

# Give Xvfb a moment to fully initialize
sleep 2

# Verify Xvfb is running
if ps -p $XVFB_PID > /dev/null; then
    echo "✅ Xvfb started successfully (PID: $XVFB_PID)."
else
    echo "❌ Failed to start Xvfb."
    exit 1
fi

echo "Starting Alibaba Inquiry Automation..."
# Run the Python script using exec to forward OS termination signals
exec python sheet_alibaba_inquiry.py "$@"
