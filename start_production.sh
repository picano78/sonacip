#!/bin/bash

# SONACIP Quick Start Script
# Activates venv and starts Gunicorn

PROJECT_DIR="/root/sonacip"
VENV_DIR="$PROJECT_DIR/venv"

echo "=== SONACIP QUICK START ==="

# Change to project directory
cd "$PROJECT_DIR"

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if venv is active
if [ "$VIRTUAL_ENV" = "$VENV_DIR" ]; then
    echo "✅ Virtual environment activated"
else
    echo "❌ Failed to activate virtual environment"
    exit 1
fi

# Start Gunicorn
echo "Starting Gunicorn..."
gunicorn -w 2 -b 127.0.0.1:8000 run:app
