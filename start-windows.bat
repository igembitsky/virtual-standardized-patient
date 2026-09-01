@echo off
REM Virtual Standardized Patient Simulator, Windows launcher.
REM Double-click this file. It runs serve.ps1 with the PowerShell that Windows
REM already ships. That script checks Ollama, downloads the patient model if it
REM is missing, serves this folder on http://127.0.0.1:8756, and opens your browser.
REM Nothing is installed. No administrator rights are needed. Close this window to stop.
cd /d "%~dp0"
title Virtual Standardized Patient Simulator
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0serve.ps1"
if errorlevel 1 pause
