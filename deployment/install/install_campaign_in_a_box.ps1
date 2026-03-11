# deployment/install/install_campaign_in_a_box.ps1

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " Campaign In A Box Data Platform Installation" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# 1. Check Python version
Write-Host "[1/4] Checking Python version..."

$pythonCmd = "python"
if (-Not (Get-Command $pythonCmd -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Python is not installed or not in PATH. Please install Python >= 3.10." -ForegroundColor Red
    exit 1
}

$pyVerStr = & $pythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$pyVer = [decimal]$pyVerStr
if ($pyVer -lt 3.10) {
    Write-Host "Error: Python version must be >= 3.10. Found $pyVerStr." -ForegroundColor Red
    exit 1
}
Write-Host "✓ Found Python $pyVerStr" -ForegroundColor Green

# 2. Create Virtual Environment
Write-Host "[2/4] Setting up virtual environment..."
& $pythonCmd -m venv venv
if (-Not $?) {
    Write-Host "Error creating virtual environment." -ForegroundColor Red
    exit 1
}
Write-Host "✓ Virtual environment 'venv' created." -ForegroundColor Green

# 3. Install Dependencies
Write-Host "[3/4] Installing dependencies from requirements.txt..."
& .\venv\Scripts\python.exe -m pip install --upgrade pip
& .\venv\Scripts\pip.exe install -r requirements.txt
Write-Host "✓ Dependencies installed." -ForegroundColor Green

# 4. Initialize Data Directories
Write-Host "[4/4] Initializing data directories..."
$dirs = @(
    "data/elections", "data/voters", "data/intelligence/private", "data/campaign_runtime",
    "derived", "logs", "archive", "reports", "config"
)
foreach ($d in $dirs) {
    if (-Not (Test-Path -Path $d)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
    }
}
Write-Host "✓ Directories initialized." -ForegroundColor Green

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " Installation Complete!" -ForegroundColor Cyan
Write-Host " Run the platform with: .\run_campaign_box.ps1" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
