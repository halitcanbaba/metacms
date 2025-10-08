# run.ps1 - Run the CRM-MT5-Python application
Write-Host "=== Starting CRM-MT5-Python Application ===" -ForegroundColor Cyan

# Check if virtual environment exists
if (-not (Test-Path ".venv")) {
    Write-Host "ERROR: Virtual environment not found. Please run .\scripts\setup.ps1 first" -ForegroundColor Red
    exit 1
}

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "WARNING: .env file not found. Using .env.example values..." -ForegroundColor Yellow
}

# Activate virtual environment
Write-Host "`nActivating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# Start the application
Write-Host "`nStarting FastAPI application..." -ForegroundColor Yellow
Write-Host "Access the application at: http://localhost:8000" -ForegroundColor Green
Write-Host "API documentation at: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "`nPress Ctrl+C to stop the server`n" -ForegroundColor Gray

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
