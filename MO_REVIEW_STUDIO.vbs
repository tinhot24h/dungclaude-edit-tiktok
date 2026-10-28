' Review Studio without a command window (Windows). Double-click to open; stop it with the power button in the app header.
' Python and FFmpeg run in a hidden console, so no black window appears and none flashes while exporting.
Option Explicit
Dim shell, fso, here, python
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = here
python = "python"
If shell.Run("cmd /c where py >nul 2>nul", 0, True) = 0 Then python = "py -3"
shell.Run "cmd /c " & python & " launch.py --hidden", 0, False
