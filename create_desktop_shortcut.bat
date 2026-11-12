@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo   Creating Desktop Shortcut: SPECTRA IR Camera Studio
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $desktop = [Environment]::GetFolderPath('Desktop'); $shortcutPath = [IO.Path]::Combine($desktop, 'SPECTRA IR Camera Studio.lnk'); $shortcut = $ws.CreateShortcut($shortcutPath); $shortcut.TargetPath = 'wscript.exe'; $shortcut.Arguments = '\"%~dp0launch_app.vbs\"'; $shortcut.WorkingDirectory = '%~dp0'; $shortcut.Description = 'SPECTRA Precision Infrared Studio'; $shortcut.IconLocation = '%SystemRoot%\System32\shell32.dll,19'; $shortcut.Save(); Write-Host '[+] Shortcut created at:' $shortcutPath"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [+] Success! Desktop shortcut created.
) else (
    echo.
    echo [-] Note: Could not create shortcut automatically. You can right-click 'launch_app.vbs' and select 'Send to -> Desktop'.
)

