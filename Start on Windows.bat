@echo off
rem Virtual Standardized Patient Simulator, Windows launcher.
rem Double-click this file. It starts app\server.ps1 with the PowerShell that Windows
rem already ships, with no window, and that opens your browser. Nothing is installed.
rem The simulator stops by itself when you close its browser tab, or press Quit in the page.
cd /d "%~dp0app" || exit /b 1
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -WindowStyle Hidden -WorkingDirectory $PWD -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File server.ps1'"
