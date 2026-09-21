@echo off
setlocal
cd /d "%~dp0.."

where mvn >nul 2>&1
if errorlevel 1 (
  echo Maven 3.x is required to build the Java WaifuMon engine.
  exit /b 1
)

if "%JAVA_HOME%"=="" (
  echo JAVA_HOME must point to a JDK 21 installation.
  exit /b 1
)

if not exist "%JAVA_HOME%\bin\jlink.exe" (
  echo JDK 21 jlink.exe was not found under JAVA_HOME.
  exit /b 1
)

set "ENGINE_STAGE=.waifumon-runtime"

if exist "%ENGINE_STAGE%" rmdir /s /q "%ENGINE_STAGE%"
mkdir "%ENGINE_STAGE%"

mvn --batch-mode --no-transfer-progress -f engine\waifumon\pom.xml clean package -DskipTests
if errorlevel 1 exit /b %errorlevel%

copy /Y engine\waifumon\target\waifumon-engine.jar "%ENGINE_STAGE%\waifumon-engine.jar" >nul
if errorlevel 1 exit /b %errorlevel%

"%JAVA_HOME%\bin\jlink.exe" ^
  --add-modules java.base ^
  --strip-debug ^
  --no-man-pages ^
  --no-header-files ^
  --compress=2 ^
  --output "%ENGINE_STAGE%\jre"
if errorlevel 1 exit /b %errorlevel%

if not exist "%ENGINE_STAGE%\waifumon-engine.jar" (
  echo Staged WaifuMon engine JAR was not created.
  exit /b 1
)
if not exist "%ENGINE_STAGE%\jre\bin\java.exe" (
  echo Staged Java runtime executable was not created.
  exit /b 1
)

if exist dist\engine rmdir /s /q dist\engine
xcopy "%ENGINE_STAGE%" dist\engine /E /I /Y >nul
if errorlevel 1 exit /b %errorlevel%

echo.
echo ============================================
echo WaifuMon Java engine listo.
echo.
echo JAR: dist\engine\waifumon-engine.jar
echo JRE: dist\engine\jre
echo Staging: %ENGINE_STAGE%
echo ============================================
echo.
exit /b 0
