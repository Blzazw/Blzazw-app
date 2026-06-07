@echo off
cd /d "%~dp0"
echo Starting Blzazw...
taskkill /f /im Blzazw.exe >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
timeout /t 2 /nobreak >nul
start "" "release\win-unpacked\Blzazw.exe"
echo Done
timeout /t 3 /nobreak >nul