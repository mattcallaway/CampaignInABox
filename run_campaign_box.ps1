# run_campaign_box.ps1

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $scriptPath

if (-Not (Test-Path -Path "venv")) {
    Write-Host "Virtual environment not found. Please run .\deployment\install\install_campaign_in_a_box.ps1 first." -ForegroundColor Red
    exit 1
}

# Source venv
& .\venv\Scripts\Activate.ps1

# Check if Campaign Config exists, if not run setup wizard
if (-Not (Test-Path -Path "config\campaign_config.yaml")) {
    Write-Host "First time setup detected. Launching configuration wizard..." -ForegroundColor Cyan
    & python engine\setup\setup_wizard.py
}

Write-Host "Starting Campaign In A Box Dashboard..." -ForegroundColor Cyan
& streamlit run ui\dashboard\app.py
