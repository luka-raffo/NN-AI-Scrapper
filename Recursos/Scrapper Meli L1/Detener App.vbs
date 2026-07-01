Option Explicit
' Cierra el backend (por si no queda ningun CMD visible para hacer Ctrl+C).
Dim objShell, objFSO, strDir, q

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
strDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
q = Chr(34)

objShell.Run "cmd /c " & q & strDir & "\detener_silencioso.bat" & q, 0, True
MsgBox "La app quedo detenida.", vbInformation, "Nuevos Negocios AI"
