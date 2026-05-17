@echo off
setlocal EnableDelayedExpansion

set "PORT=5000"
if defined QUICKSHARE_PORT set "PORT=%QUICKSHARE_PORT%"

echo Stopping anything on port %PORT%...

set "FOUND=0"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":%PORT%" ^| findstr LISTENING') do (
    set "FOUND=1"
    echo Ending PID %%P ...
    taskkill /PID %%P /F >nul 2>&1
)

if "!FOUND!"=="0" (
    echo Nothing was listening on port %PORT%.
) else (
    echo Done.
)

pause
