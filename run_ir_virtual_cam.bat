@echo off
setlocal enabledelayedexpansion
title Windows Hello IR Virtual Camera Bridge (Discord / Zoom)
cd /d "%~dp0"

:: 1. Check local virtual environment
if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" "%~dp0ir_to_virtualcam.py" %*
    goto :handle_exit
)
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0ir_to_virtualcam.py" %*
    goto :handle_exit
)

:: 2. Try py -3.11
py -3.11 -c "import sys" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3.11 "%~dp0ir_to_virtualcam.py" %*
    goto :handle_exit
)

:: 3. Try py -3.10
py -3.10 -c "import sys" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3.10 "%~dp0ir_to_virtualcam.py" %*
    goto :handle_exit
)

:: 4. Try system python
python -c "import sys" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python "%~dp0ir_to_virtualcam.py" %*
    goto :handle_exit
)

echo.
echo ==============================================================
echo  [!] Python environment not detected or setup incomplete!
echo ==============================================================
echo  SPECTRA IR-CORE requires Python 3.10 or 3.11 with dependencies.
echo  Please run 'install.bat' to set up your environment automatically.
echo.
pause
exit /b 1

:handle_exit
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Virtual camera bridge exited with code %ERRORLEVEL%.
    pause
)
