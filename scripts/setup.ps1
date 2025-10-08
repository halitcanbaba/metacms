# setup.ps1 - Setup script for CRM-MT5-Python project
Write-Host "=== CRM-MT5-Python Setup ===" -ForegroundColor Cyan

# Check Python version
Write-Host "`n[1/6] Checking Python installation..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    exit 1
}
Write-Host "Found: $pythonVersion" -ForegroundColor Green

# Check if we're in the right directory
if (-not (Test-Path "requirements.txt")) {
    Write-Host "ERROR: requirements.txt not found. Please run this script from the project root." -ForegroundColor Red
    exit 1
}

# Create virtual environment
Write-Host "`n[2/6] Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path ".venv") {
    Write-Host "Virtual environment already exists. Skipping..." -ForegroundColor Gray
} else {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
    Write-Host "Virtual environment created successfully" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "`n[3/6] Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to activate virtual environment" -ForegroundColor Red
    exit 1
}
Write-Host "Virtual environment activated" -ForegroundColor Green

# Upgrade pip
Write-Host "`n[4/6] Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet
Write-Host "pip upgraded successfully" -ForegroundColor Green

# Install dependencies
Write-Host "`n[5/6] Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
    exit 1
}
Write-Host "Dependencies installed successfully" -ForegroundColor Green

# Copy .env.example to .env if not exists
Write-Host "`n[6/6] Setting up environment file..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host ".env file already exists. Skipping..." -ForegroundColor Gray
} else {
    Copy-Item ".env.example" ".env"
    Write-Host ".env file created from .env.example" -ForegroundColor Green
    Write-Host "IMPORTANT: Please edit .env file with your configuration!" -ForegroundColor Magenta
}

# Setup Tailwind CSS (basic setup)
Write-Host "`n[Bonus] Setting up Tailwind CSS..." -ForegroundColor Yellow
if (Test-Path "app\ui\static\css") {
    Write-Host "CSS directory already exists" -ForegroundColor Gray
} else {
    New-Item -ItemType Directory -Force -Path "app\ui\static\css" | Out-Null
    Write-Host "CSS directory created" -ForegroundColor Green
}

# Create a basic Tailwind config note
$tailwindNote = @"
# Tailwind CSS Setup
# For production, install Tailwind CLI:
# npm install -D tailwindcss
# npx tailwindcss init
# npx tailwindcss -i ./app/ui/static/css/input.css -o ./app/ui/static/css/output.css --watch
"@
Set-Content -Path "app\ui\static\css\README.md" -Value $tailwindNote

Write-Host "`n=== Setup Complete! ===" -ForegroundColor Cyan
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Edit .env file with your configuration (MT5, Pipedrive, Database)" -ForegroundColor White
Write-Host "2. Run database migrations: .\scripts\migrate.ps1" -ForegroundColor White
Write-Host "3. Start the application: .\scripts\run.ps1" -ForegroundColor White
Write-Host "`nNote: Keep the virtual environment activated or run:" -ForegroundColor Yellow
Write-Host ".\.venv\Scripts\Activate.ps1" -ForegroundColor White
