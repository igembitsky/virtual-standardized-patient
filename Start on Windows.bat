@echo off
rem Virtual Standardized Patient Simulator, Windows launcher.
rem Double-click this file. It starts app\server.ps1 with the PowerShell that Windows
rem already ships, with no window, and that opens your browser. Nothing is installed.
rem The simulator stops by itself when you close its browser tab, or press Quit in the page.
rem If Windows will not let the script run at all, it opens app\problem.html to report it.
rem ($h keeps the handle, without which Windows PowerShell forgets the exit code.)
cd /d "%~dp0app" || exit /b 1
start "" /min powershell -NoProfile -WindowStyle Hidden -Command "$p = Start-Process powershell -WindowStyle Hidden -WorkingDirectory $PWD -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File server.ps1' -PassThru; $h = $p.Handle; if ($p.WaitForExit(6000) -and $p.ExitCode -notin 0,3) { Start-Process (Resolve-Path problem.html).Path }"
