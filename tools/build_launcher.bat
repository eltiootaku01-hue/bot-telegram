@echo off
setlocal
python -m pip install -e ".[dev]"
python -m pip install pyinstaller
if errorlevel 1 exit /b %errorlevel%

if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
mkdir dist\bots

pyinstaller --noconfirm --clean --console --onefile --name Cari --distpath dist\bots --workpath build\Cari app\bots\cari.py
if errorlevel 1 exit /b %errorlevel%
pyinstaller --noconfirm --clean --console --onefile --name Sunna --distpath dist\bots --workpath build\Sunna app\bots\sunna.py
if errorlevel 1 exit /b %errorlevel%
pyinstaller --noconfirm --clean --console --onefile --name Cami --distpath dist\bots --workpath build\Cami app\bots\cami.py
if errorlevel 1 exit /b %errorlevel%
pyinstaller --noconfirm --clean --console --onefile --name Chie --distpath dist\bots --workpath build\Chie app\bots\chie.py
if errorlevel 1 exit /b %errorlevel%
pyinstaller --noconfirm --clean --windowed --onefile --name BotManager --distpath dist --workpath build\BotManager app\launcher.py
if errorlevel 1 exit /b %errorlevel%

echo.
echo Build completo.
echo BotManager: dist\BotManager.exe
echo Bots:       dist\bots\Cari.exe, Sunna.exe, Cami.exe, Chie.exe
echo.
pause
