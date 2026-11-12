@echo off
setlocal enabledelayedexpansion
title SPECTRA // IR-CORE - Setup & Installation
cd /d "%~dp0"

echo ============================================================
echo   SPECTRA // IR-CORE - Precision Infrared Studio Installer
echo ============================================================
echo.

:: Detect Python executable (prefer 3.11 or 3.10 for winsdk binary compatibility)
set "PY_CMD="

py -3.11 -c "import sys; exit(0)" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PY_CMD=py -3.11"
    goto :python_found
)

py -3.10 -c "import sys; exit(0)" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PY_CMD=py -3.10"
    goto :python_found
)

python -c "import sys; exit(0 if sys.version_info[0] == 3 and sys.version_info[1] in (10, 11) else 1)" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PY_CMD=python"
    goto :python_found
)

:: Check if any python is in PATH
python -c "import sys; exit(0)" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=*" %%v in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"') do set "DETECTED_VER=%%v"
    echo [WARNING] Detected Python !DETECTED_VER!.
    echo 'winsdk' precompiled wheels are officially provided for Python 3.10 and 3.11.
    echo If package installation fails, please install Python 3.11 (64-bit) from python.org.
    echo.
    set "PY_CMD=python"
    goto :python_found
)

echo [ERROR] Python was not found on your system!
echo Please install Python 3.11 (64-bit) from https://www.python.org/downloads/
echo Make sure to check "Add Python to PATH" during installation.
echo.
pause
exit /b 1

:python_found
echo [*] Using Python: %PY_CMD%
%PY_CMD% --version
echo.

:: Create virtual environment
if not exist "%~dp0venv\Scripts\python.exe" (
    echo [*] Creating virtual environment in .\venv ...
    %PY_CMD% -m venv "%~dp0venv"
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [+] Virtual environment created.
) else (
    echo [*] Existing virtual environment found in .\venv.
)

:: Upgrade pip and install dependencies
echo [*] Upgrading pip...
"%~dp0venv\Scripts\python.exe" -m pip install --upgrade pip

echo [*] Installing dependencies from requirements.txt...
"%~dp0venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to install one or more dependencies.
    echo Note: 'winsdk' requires Python 3.10 or 3.11 on Windows.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Installation Successful!
echo ============================================================
echo.
echo Launch options:
echo   - run_studio_app.bat        : Primary Cyber-Tactical Studio App
echo   - launch_app.vbs            : Silent desktop launcher (no console window)
echo   - run_ir_viewer.bat         : Fast standalone OpenCV viewer
echo   - run_ir_virtual_cam.bat    : Headless OBS virtual camera bridge
echo.

set /p MAKE_SHORTCUT="Create a Desktop shortcut now? (Y/N) [default: Y]: "
if /i "!MAKE_SHORTCUT!"=="" set MAKE_SHORTCUT=Y
if /i "!MAKE_SHORTCUT!"=="Y" (
    call "%~dp0create_desktop_shortcut.bat"
)

echo.
echo Setup finished. Press any key to exit.
pause >nul

