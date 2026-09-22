@echo off
setlocal
cd /d "%~dp0.."


python -m pip install -e ".[dev]"
if errorlevel 1 exit /b %errorlevel%
python -m pip install pyinstaller==6.22.2 pyinstaller-hooks-contrib==2026.7
if errorlevel 1 exit /b %errorlevel%

if exist assets xcopy assets dist\assets /E /I /Y >nul

pyinstaller --noconfirm --clean --console --onefile --name Cari --distpath dist\bots --workpath build\Cari app\bots\cari.py
if errorlevel 1 exit /b %errorlevel%
pyinstaller --noconfirm --clean --console --onefile --name Sunna --distpath dist\bots --workpath build\Sunna app\bots\sunna.py
if errorlevel 1 exit /b %errorlevel%
pyinstaller --noconfirm --clean --console --onefile --name Cami --distpath dist\bots --workpath build\Cami app\bots\cami.py
if errorlevel 1 exit /b %errorlevel%
pyinstaller --noconfirm --clean --console --onefile --name Chie --distpath dist\bots --workpath build\Chie app\bots\chie.py
if errorlevel 1 exit /b %errorlevel%
pyinstaller --noconfirm --clean --console --onefile --name WorldBot --distpath dist\bots --workpath build\WorldBot app\bots\world.py
if errorlevel 1 exit /b %errorlevel%
pyinstaller --noconfirm --clean --windowed --onefile --name BotManager --distpath dist --workpath build\BotManager app\launcher.py
if errorlevel 1 exit /b %errorlevel%

call tools\build_waifumon.bat
if errorlevel 1 exit /b %errorlevel%

echo.
echo ============================================
echo Build completo.
echo.
echo Java:      dist\engine\waifumon-engine.jar
echo Runtime:   dist\engine\jre\bin\java.exe
echo Iniciador: dist\BotManager.exe
echo Java:      dist\engine\waifumon-engine.jar
echo Runtime:   dist\engine\jre
echo Bots:      dist\bots\Cari.exe
echo           dist\bots\Sunna.exe
echo           dist\bots\Cami.exe
echo           dist\bots\Chie.exe
echo           dist\bots\WorldBot.exe
echo ============================================
echo.
exit /b 0
