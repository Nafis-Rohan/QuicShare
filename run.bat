@echo off
setlocal EnableDelayedExpansion

REM QuickShare — fixed to D:\QuickShare (no files/cache on C:)
set "ROOT=D:\QuickShare"
set "PORT=5000"
if defined QUICKSHARE_PORT set "PORT=%QUICKSHARE_PORT%"
cd /d "%ROOT%"

REM Temp + pip cache stay on D:
set "TMP=%ROOT%\.tmp"
set "TEMP=%ROOT%\.tmp"
if not exist "%TMP%" mkdir "%TMP%"

set "PIP_CACHE_DIR=%ROOT%\.pip-cache"
if not exist "%PIP_CACHE_DIR%" mkdir "%PIP_CACHE_DIR%"

REM Virtualenv on D: (packages install here, not C:\Users\...\AppData)
if not exist "%ROOT%\venv\Scripts\activate.bat" (
    echo Creating virtual environment at D:\QuickShare\venv ...
    python -m venv "%ROOT%\venv"
)
call "%ROOT%\venv\Scripts\activate.bat"

python -c "import flask" 2>nul
if errorlevel 1 (
    echo Installing dependencies into D:\QuickShare\venv ...
    pip install -r "%ROOT%\requirements.txt"
)

REM Free port if a previous QuickShare/Python server is still running
set "BLOCKING_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":%PORT%" ^| findstr LISTENING') do set "BLOCKING_PID=%%P"

if defined BLOCKING_PID (
    echo.
    echo Port %PORT% is in use ^(PID !BLOCKING_PID!^).
    tasklist /FI "PID eq !BLOCKING_PID!" 2>nul | findstr /I "python.exe" >nul
    if !errorlevel! equ 0 (
        echo Stopping previous QuickShare instance...
        taskkill /PID !BLOCKING_PID! /F >nul 2>&1
        ping -n 3 127.0.0.1 >nul
    ) else (
        echo ERROR: Another program is using port %PORT%.
        echo Close that app, or add this line to run.bat: set QUICKSHARE_PORT=5001
        pause
        exit /b 1
    )
)

echo.
echo Starting QuickShare server on port %PORT%...
echo.

set "QUICKSHARE_PORT=%PORT%"
python -m backend.app

pause
