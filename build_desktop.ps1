$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    python -m pip install --upgrade pyinstaller
}

$env:PYTHONPATH = Join-Path $root "src"
Remove-Item -Recurse -Force "build", "dist" -ErrorAction SilentlyContinue

pyinstaller --noconfirm --clean --onefile --windowed --name bot desktop.py

New-Item -ItemType Directory -Force -Path "release" | Out-Null
Copy-Item "dist\bot.exe" "release\bot.exe" -Force
Copy-Item "config" "release\config" -Recurse -Force
if (Test-Path "biblioteca") { Copy-Item "biblioteca" "release\biblioteca" -Recurse -Force }
if (Test-Path ".env.example") { Copy-Item ".env.example" "release\.env.example" -Force }

Write-Host "BOT-IA desktop generado en release\bot.exe"
Write-Host "Copia tu .env real y configura las rutas de biblioteca antes de usarlo."
