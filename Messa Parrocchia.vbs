' Avvio di Messa Parrocchia senza finestre nere (solo caratteri ASCII).
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
py = dir & "\.venv\Scripts\pythonw.exe"
If Not fso.FileExists(py) Then
  MsgBox "Prima di usare il programma serve l'installazione (una volta sola)." & vbCrLf & vbCrLf & _
         "Nella cartella del programma fai doppio clic su ""Installa.bat"".", 48, "Messa Parrocchia"
  WScript.Quit 1
End If
sh.CurrentDirectory = dir
sh.Run """" & py & """ """ & dir & "\app.py""", 0, False
