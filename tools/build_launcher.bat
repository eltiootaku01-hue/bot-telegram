@echo off
setlocal
python -m pip install -e ".[dev]"
python -m pip install pyinstaller
pyinstaller --noconfirm --clean --name BotManager --windowed --onefile app\launcher.py
if errorlevel 1 exit /b %errorlevel%
echo.
echo BotManager.exe creado en dist\BotManager.exe
echo.
pause
