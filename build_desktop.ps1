$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    python -m pip install --upgrade pyinstaller
}

$env:PYTHONPATH = Join-Path $root "src"
Remove-Item -Recurse -Force "build", "dist", "release" -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path "release" | Out-Null

pyinstaller --noconfirm --clean --onefile --windowed --name BOT-IA-Core desktop.py
pyinstaller --noconfirm --clean --onefile --windowed --name BOT-IA launcher.py

Copy-Item "dist\BOT-IA-Core.exe" "release\BOT-IA-Core.exe" -Force
Copy-Item "dist\BOT-IA.exe" "release\BOT-IA.exe" -Force
Copy-Item "config" "release\config" -Recurse -Force
if (Test-Path "biblioteca") { Copy-Item "biblioteca" "release\biblioteca" -Recurse -Force }
if (Test-Path ".env.example") { Copy-Item ".env.example" "release\.env.example" -Force }

Write-Host "BOT-IA generado en release\BOT-IA.exe"
Write-Host "El launcher configura la primera ejecución y después inicia BOT-IA-Core.exe."
