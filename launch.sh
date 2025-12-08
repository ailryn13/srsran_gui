#!/bin/bash
# Launcher script for srsRAN GUI

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    echo "Please install Python 3.6 or higher"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.6"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "Error: Python $REQUIRED_VERSION or higher is required"
    echo "Current version: $PYTHON_VERSION"
    exit 1
fi

# Check if requirements are installed
if ! python3 -c "import psutil" &> /dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Run the GUI
echo "Starting srsRAN GUI..."
python3 srsran_gui.py
