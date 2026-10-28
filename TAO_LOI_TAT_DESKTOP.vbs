' Creates a "Review Studio" shortcut on the desktop that opens the app without a command window.
Option Explicit
Dim shell, fso, here, link
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
Set link = shell.CreateShortcut(shell.SpecialFolders("Desktop") & "\Review Studio.lnk")
link.TargetPath = shell.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\wscript.exe"
link.Arguments = """" & here & "\MO_REVIEW_STUDIO.vbs" & """"
link.WorkingDirectory = here
link.IconLocation = shell.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\imageres.dll,18"
link.Description = "Review Studio"
link.Save
MsgBox "Da tao loi tat ""Review Studio"" tren Desktop. Bam vao do de mo ung dung, khong hien cua so cmd.", 64, "Review Studio"
