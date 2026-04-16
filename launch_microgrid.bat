@echo off
cd /d "%~dp0"
TITLE Honeybee Control Center
COLOR 0A

echo =======================================================
echo          HONEYBEE LAUNCHER v1.1
echo =======================================================
echo.

:: --- CHECK BACKEND ---
echo [1/2] Preparing Backend...
if exist .venv\Scripts\python.exe (
    echo Found virtual environment. Using .venv...
    start "HONEYBEE BACKEND" cmd /k ".venv\Scripts\python.exe start_microgrid.py"
) else (
    echo No virtual environment found. Using system python...
    start "HONEYBEE BACKEND" cmd /k "python start_microgrid.py"
)

:: --- CHECK FRONTEND ---
echo [2/2] Preparing Frontend...
pushd dashboard
if not exist node_modules (
    echo node_modules missing. Installing dependencies (this may take a minute^)...
    call npm install
)
start "HONEYBEE DASHBOARD" cmd /k "npm run dev"
popd

echo.
echo -------------------------------------------------------
echo SUCCESS: Launcher tasks dispatched.
echo -------------------------------------------------------
echo.
pause
