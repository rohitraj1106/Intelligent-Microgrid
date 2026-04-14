@echo off
TITLE Microgrid Control Center
COLOR 0A

echo =======================================================
echo          INTELLIGENT MICROGRID LAUNCHER v1.1
echo =======================================================
echo.

:: --- CHECK BACKEND ---
echo [1/2] Preparing Backend...
if exist .venv\Scripts\python.exe (
    echo Found virtual environment. Using .venv...
    start "MICROGRID BACKEND" cmd /k ".venv\Scripts\python.exe start_microgrid.py"
) else (
    echo No virtual environment found. Using system python...
    start "MICROGRID BACKEND" cmd /k "python start_microgrid.py"
)

:: --- CHECK FRONTEND ---
echo [2/2] Preparing Frontend...
cd dashboard
if not exist node_modules (
    echo node_modules missing. Installing dependencies (this may take a minute^)...
    call npm install
)
start "MICROGRID DASHBOARD" cmd /k "npm run dev"
cd ..

echo.
echo -------------------------------------------------------
echo SUCCESS: Launcher tasks dispatched.
echo -------------------------------------------------------
echo.
pause
