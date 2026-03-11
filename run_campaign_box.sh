#!/usr/bin/env bash
# run_campaign_box.sh
set -e

# Change to script directory
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Please run ./deployment/install/install_campaign_in_a_box.sh first."
    exit 1
fi

source venv/bin/activate

# Check if Campaign Config exists, if not run setup wizard
if [ ! -f "config/campaign_config.yaml" ]; then
    echo "First time setup detected. Launching configuration wizard..."
    python engine/setup/setup_wizard.py
fi

echo "Starting Campaign In A Box Dashboard..."
streamlit run ui/dashboard/app.py
