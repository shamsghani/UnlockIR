' SPECTRA // IR-CORE - Precision Infrared Studio Launcher
' Launches the studio app server windowlessly (no terminal / black command prompt window)
Option Explicit

Dim WshShell, FSO, ScriptDir, PythonwExe, AppScript, ExitCode

Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
AppScript = """" & ScriptDir & "\app_server.py"""

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = ScriptDir

' 1. Check local virtual environment
If FSO.FileExists(ScriptDir & "\venv\Scripts\pythonw.exe") Then
    PythonwExe = """" & ScriptDir & "\venv\Scripts\pythonw.exe"""
ElseIf FSO.FileExists(ScriptDir & "\.venv\Scripts\pythonw.exe") Then
    PythonwExe = """" & ScriptDir & "\.venv\Scripts\pythonw.exe"""
Else
    ' 2. Fallback to pyw Windows launcher
    PythonwExe = "pyw -3.11"
End If

On Error Resume Next
ExitCode = WshShell.Run(PythonwExe & " " & AppScript, 0, False)

If Err.Number <> 0 Then
    Err.Clear
    ' Fallback to pyw generic or pythonw
    ExitCode = WshShell.Run("pyw " & AppScript, 0, False)
    If Err.Number <> 0 Then
        Err.Clear
        ExitCode = WshShell.Run("pythonw " & AppScript, 0, False)
        If Err.Number <> 0 Then
            MsgBox "Failed to launch SPECTRA IR Studio." & vbCrLf & vbCrLf & _
                   "Python 3.10/3.11 environment not found or not configured." & vbCrLf & _
                   "Please run 'install.bat' to automatically set up the environment.", _
                   vbCritical, "SPECTRA IR-CORE"
        End If
    End If
End If
