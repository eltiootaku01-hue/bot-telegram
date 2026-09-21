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

if exist "dist\engine" rmdir /s /q "dist\engine"
mkdir "dist\engine"
if errorlevel 1 exit /b %errorlevel%

mvn --batch-mode --no-transfer-progress -f engine\waifumon\pom.xml clean package -DskipTests
if errorlevel 1 exit /b %errorlevel%

copy /Y "engine\waifumon\target\waifumon-engine.jar" "dist\engine\waifumon-engine.jar" >nul
if errorlevel 1 exit /b %errorlevel%

"%JAVA_HOME%\bin\jlink.exe" ^
  --add-modules java.base ^
  --strip-debug ^
  --no-man-pages ^
  --no-header-files ^
  --compress=2 ^
  --output "dist\engine\jre"
if errorlevel 1 exit /b %errorlevel%

if not exist "dist\engine\waifumon-engine.jar" (
  echo Final WaifuMon engine JAR was not created.
  exit /b 1
)
if not exist "dist\engine\jre\bin\java.exe" (
  echo Final bundled Java runtime executable was not created.
  exit /b 1
)

for %%F in ("dist\engine\waifumon-engine.jar") do if %%~zF LSS 100KB (
  echo Final WaifuMon engine JAR is unexpectedly small.
  exit /b 1
)
for %%F in ("dist\engine\jre\bin\java.exe") do if %%~zF LSS 100KB (
  echo Final bundled Java runtime executable is unexpectedly small.
  exit /b 1
)

echo.
echo ============================================
echo WaifuMon Java engine listo.
echo.
echo JAR: dist\engine\waifumon-engine.jar
echo JRE: dist\engine\jre
echo ============================================
echo.
exit /b 0
