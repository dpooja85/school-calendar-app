#!/bin/bash
# School Calendar App - Setup Script
# ===================================
# Run this once after cloning the repo:
#   chmod +x setup.sh && ./setup.sh

set -e

echo "=================================================="
echo "School Calendar App - Setup"
echo "=================================================="
echo

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo "Error: Homebrew not installed."
    echo "Install it from: https://brew.sh"
    exit 1
fi
echo "✓ Homebrew found"

# Check/install Python
if ! command -v python3 &> /dev/null; then
    echo "Installing Python..."
    brew install python
else
    echo "✓ Python found"
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "✓ Virtual environment exists"
fi

# Activate venv and install dependencies
echo "Installing Python dependencies..."
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ Python dependencies installed"

# Check/install Ollama
if ! command -v ollama &> /dev/null; then
    echo "Installing Ollama..."
    brew install ollama
else
    echo "✓ Ollama found"
fi

# Start Ollama service
echo "Starting Ollama service..."
brew services start ollama 2>/dev/null || true
sleep 2

# Pull the model if not already downloaded
MODEL="llama3.1:8b"
echo "Checking for $MODEL model..."
if ! ollama list 2>/dev/null | grep -q "llama3.1"; then
    echo "Downloading $MODEL model (~4.7GB, this may take a few minutes)..."
    ollama pull $MODEL
else
    echo "✓ $MODEL model found"
fi

# Create input_emails folder if needed
mkdir -p input_emails
mkdir -p output

echo
echo "=================================================="
echo "Setup Complete!"
echo "=================================================="
echo
echo "Next steps:"
echo "1. Add your credentials.json (Google OAuth)"
echo "2. Run: source venv/bin/activate"
echo "3. Run: python main.py --preview"
echo
