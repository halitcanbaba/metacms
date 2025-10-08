# create_admin.ps1 - Create an admin user for the CRM system
param(
    [Parameter(Mandatory=$false)]
    [string]$Email = "admin@example.com",
    
    [Parameter(Mandatory=$false)]
    [string]$Password = "admin123",
    
    [Parameter(Mandatory=$false)]
    [string]$FullName = "System Administrator"
)

Write-Host "=== Create Admin User ===" -ForegroundColor Cyan

# Check if virtual environment exists
if (-not (Test-Path ".venv")) {
    Write-Host "ERROR: Virtual environment not found. Please run .\scripts\setup.ps1 first" -ForegroundColor Red
    exit 1
}

# Activate virtual environment
Write-Host "`nActivating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# Create Python script to add admin user
$pythonScript = @"
import asyncio
import sys
sys.path.insert(0, '.')

from app.db import AsyncSessionLocal
from app.repositories.users_repo import UsersRepository
from app.domain.enums import UserRole

async def create_admin(email: str, password: str, full_name: str):
    async with AsyncSessionLocal() as db:
        try:
            repo = UsersRepository(db)
            
            # Check if user already exists
            existing = await repo.get_by_email(email)
            if existing:
                print(f'ERROR: User with email {email} already exists')
                return False
            
            # Create admin user
            user = await repo.create(
                email=email,
                password=password,
                role=UserRole.ADMIN,
                full_name=full_name
            )
            await db.commit()
            
            print(f'SUCCESS: Admin user created')
            print(f'  Email: {user.email}')
            print(f'  Role: {user.role}')
            print(f'  Name: {user.full_name}')
            return True
            
        except Exception as e:
            print(f'ERROR: Failed to create admin user: {e}')
            return False

if __name__ == '__main__':
    email = sys.argv[1] if len(sys.argv) > 1 else 'admin@example.com'
    password = sys.argv[2] if len(sys.argv) > 2 else 'admin123'
    full_name = sys.argv[3] if len(sys.argv) > 3 else 'System Administrator'
    
    success = asyncio.run(create_admin(email, password, full_name))
    sys.exit(0 if success else 1)
"@

# Write Python script to temp file
$tempScript = [System.IO.Path]::GetTempFileName()
$pythonFile = "$tempScript.py"
Set-Content -Path $pythonFile -Value $pythonScript

Write-Host "`nCreating admin user..." -ForegroundColor Yellow
Write-Host "  Email: $Email" -ForegroundColor Gray
Write-Host "  Full Name: $FullName" -ForegroundColor Gray

# Run the Python script
python $pythonFile $Email $Password $FullName
$exitCode = $LASTEXITCODE

# Clean up
Remove-Item $tempScript -ErrorAction SilentlyContinue
Remove-Item $pythonFile -ErrorAction SilentlyContinue

if ($exitCode -eq 0) {
    Write-Host "`n=== Admin User Created Successfully ===" -ForegroundColor Green
    Write-Host "`nYou can now login with:" -ForegroundColor Yellow
    Write-Host "  Email: $Email" -ForegroundColor White
    Write-Host "  Password: [hidden]" -ForegroundColor White
    Write-Host "`nIMPORTANT: Change the password immediately after first login!" -ForegroundColor Magenta
} else {
    Write-Host "`n=== Failed to Create Admin User ===" -ForegroundColor Red
    exit 1
}
