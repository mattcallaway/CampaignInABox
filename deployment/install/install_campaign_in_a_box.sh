#!/usr/bin/env bash
# deployment/install/install_campaign_in_a_box.sh
set -e

echo "=============================================="
echo " Campaign In A Box Data Platform Installation"
echo "=============================================="

# 1. Check Python version
echo "[1/4] Checking Python version..."
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python is not installed. Please install Python >= 3.10."
    exit 1
fi

PY_VER=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [[ $(echo "$PY_VER < 3.10" | bc -l) -eq 1 ]]; then
    echo "Error: Python version must be >= 3.10. Found $PY_VER."
    exit 1
fi
echo "✓ Found Python $PY_VER"

# 2. Create Virtual Environment
echo "[2/4] Setting up virtual environment..."
$PYTHON_CMD -m venv venv
source venv/bin/activate
echo "✓ Virtual environment 'venv' created and activated."

# 3. Install Dependencies
echo "[3/4] Installing dependencies from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Dependencies installed."

# 4. Initialize Data Directories
echo "[4/4] Initializing data directories..."
mkdir -p data/elections data/voters data/intelligence/private data/campaign_runtime
mkdir -p derived logs archive reports
echo "✓ Directories initialized."

echo "=============================================="
echo " Installation Complete!"
echo " Run the platform with: ./run_campaign_box.sh"
echo "=============================================="
