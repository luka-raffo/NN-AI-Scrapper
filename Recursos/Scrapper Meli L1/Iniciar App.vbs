Option Explicit
' ============================================================
'  Lanzador tipo "programa de escritorio": sin ventana de CMD.
'  - Si el backend no esta corriendo, lo levanta oculto
'    (iniciar_silencioso.bat) y espera a que responda.
'  - Si ya estaba corriendo, no abre otro (evita el error de
'    puerto ocupado).
'  - En los dos casos, abre el navegador con la app al final.
' ============================================================

Dim objShell, objFSO, strDir, q, ok, i

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
strDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
q = Chr(34)

If Not BackendVivo() Then
    objShell.Run "cmd /c " & q & strDir & "\iniciar_silencioso.bat" & q, 0, False

    ok = False
    For i = 1 To 25
        WScript.Sleep 1000
        If BackendVivo() Then
            ok = True
            Exit For
        End If
    Next

    If Not ok Then
        MsgBox "No se pudo iniciar la app despues de esperar unos segundos." & vbCrLf & vbCrLf & _
               "Verifica que Python este instalado (python.org, tildando 'Add to PATH')." & vbCrLf & _
               "Para ver el detalle del error, ejecuta 'start.bat' en esta misma carpeta.", _
               vbExclamation, "Nuevos Negocios AI"
        WScript.Quit 1
    End If
End If

objShell.Run "http://127.0.0.1:8000/"

Function BackendVivo()
    Dim http
    On Error Resume Next
    Set http = CreateObject("MSXML2.XMLHTTP")
    http.Open "GET", "http://127.0.0.1:8000/health", False
    http.Send
    If Err.Number <> 0 Then
        BackendVivo = False
    Else
        BackendVivo = (http.Status = 200)
    End If
    Err.Clear
    On Error Goto 0
End Function
