# One-shot setup: install deps, create storage dir, run DB migrations.
# Run from the project root:    .\scripts\setup.ps1

$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
Set-Location $root

if (-not (Test-Path .env)) {
    Write-Host ".env not found. Copying from .env.example..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "Edit .env now with your GROQ_API_KEY, GEMINI_API_KEY, JWT_SECRET, NEXTAUTH_SECRET." -ForegroundColor Yellow
    Write-Host "Re-run this script after editing." -ForegroundColor Yellow
    exit 1
}

# --- Backend: Python venv + deps ---
Write-Host "[1/4] Backend: creating venv and installing deps..." -ForegroundColor Cyan
Set-Location backend
if (-not (Test-Path .venv)) {
    python -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements.txt

# --- Storage dir ---
Write-Host "[2/4] Creating storage directory..." -ForegroundColor Cyan
Set-Location $root
$storageDir = (Get-Content .env | Select-String "^STORAGE_DIR=").ToString().Split("=", 2)[1].Trim()
if ([string]::IsNullOrWhiteSpace($storageDir)) { $storageDir = "./data/files" }
New-Item -ItemType Directory -Force -Path $storageDir | Out-Null

# --- Run Alembic ---
Write-Host "[3/4] Running database migrations..." -ForegroundColor Cyan
Set-Location backend
# Load .env vars into the current shell so alembic sees them
Get-Content ..\.env | ForEach-Object {
    if ($_ -match "^\s*([^#=]+)=(.*)$") {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        Set-Item -Path "Env:$name" -Value $value
    }
}
.\.venv\Scripts\alembic.exe upgrade head

# --- Frontend: npm install ---
Write-Host "[4/4] Frontend: npm install..." -ForegroundColor Cyan
Set-Location $root\frontend
npm install

Set-Location $root
Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Start the three services in separate terminals:" -ForegroundColor Green
Write-Host "  .\scripts\start-api.ps1" -ForegroundColor Gray
Write-Host "  .\scripts\start-worker.ps1" -ForegroundColor Gray
Write-Host "  .\scripts\start-frontend.ps1" -ForegroundColor Gray
