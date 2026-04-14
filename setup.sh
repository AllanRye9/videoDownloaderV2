#!/bin/bash

echo "=================================="
echo "Video Downloader - Setup Script"
echo "=================================="
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
required_version="3.8"

if (( $(echo "$python_version < $required_version" | bc -l) )); then
    echo "❌ Python 3.8 or higher is required. You have Python $python_version"
    exit 1
fi

echo "✅ Python $python_version detected"
echo ""

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️  ffmpeg not found. Installing..."
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt update && sudo apt install -y ffmpeg
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v brew &> /dev/null; then
            brew install ffmpeg
        else
            echo "❌ Please install Homebrew first: https://brew.sh/"
            exit 1
        fi
    else
        echo "❌ Please install ffmpeg manually: https://ffmpeg.org/download.html"
        exit 1
    fi
fi

echo "✅ ffmpeg installed"
echo ""

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "✅ Created .env file. Please edit it with your settings."
else
    echo "✅ .env file already exists"
fi

# Create downloads directory
mkdir -p downloads
echo "✅ Downloads directory created"

echo ""
echo "=================================="
echo "🎉 Setup complete!"
echo "=================================="
echo ""
echo "To start the server:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Run the server: python app.py"
echo ""
echo "Or use Docker:"
echo "  docker-compose up"
echo ""
echo "Server will be available at: http://localhost:5000"
echo ""
