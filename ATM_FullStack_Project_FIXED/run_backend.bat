@echo off
title OOP Bank ATM - Backend
cd /d "%~dp0"

echo ==========================================
echo       OOP BANK ATM - STARTING SERVER
echo ==========================================
echo.
echo Installing/checking backend packages...
py -m pip install -r backend\requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Python packages could not be installed.
    echo Please make sure Python is installed and try again.
    pause
    exit /b 1
)

echo.
echo Opening ATM at http://127.0.0.1:5000
start "" http://127.0.0.1:5000

echo.
echo Backend is running. Keep this window OPEN.
echo Close this window to stop the ATM server.
echo.
py backend\app.py

echo.
echo Backend stopped.
pause
