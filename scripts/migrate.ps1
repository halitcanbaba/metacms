# migrate.ps1 - Database migration script for CRM-MT5-Python
Write-Host "=== Running Database Migrations ===" -ForegroundColor Cyan

# Check if virtual environment exists
if (-not (Test-Path ".venv")) {
    Write-Host "ERROR: Virtual environment not found. Please run .\scripts\setup.ps1 first" -ForegroundColor Red
    exit 1
}

# Activate virtual environment
Write-Host "`nActivating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# Check if alembic.ini exists
if (-not (Test-Path "app\alembic.ini")) {
    Write-Host "WARNING: alembic.ini not found. Alembic might not be initialized yet." -ForegroundColor Yellow
    Write-Host "The application should initialize it on first run." -ForegroundColor Yellow
    exit 0
}

# Run migrations
Write-Host "`nRunning Alembic migrations..." -ForegroundColor Yellow
Set-Location app
alembic upgrade head
$exitCode = $LASTEXITCODE
Set-Location ..

if ($exitCode -ne 0) {
    Write-Host "`nERROR: Migration failed" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== Migrations Complete! ===" -ForegroundColor Green
