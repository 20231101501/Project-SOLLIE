Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\\Users\\My PC\\Documents\\GitHub\\Project-SOLLIE\\files"
shell.Run Chr(34) & "C:\\Users\\My PC\\AppData\\Local\\Python\\pythoncore-3.14-64\\pythonw.exe" & Chr(34) & _
" " & Chr(34) & "C:\\Users\\My PC\\Documents\\GitHub\\Project-SOLLIE\\files\\sollie_launcher.py" & Chr(34), 0, False
