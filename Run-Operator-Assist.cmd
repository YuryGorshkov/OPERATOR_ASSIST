@echo off
set SCRIPT_DIR=%~dp0
set PYTHONW=C:\Users\79615\AppData\Local\Programs\Python\Python310\pythonw.exe
set PYTHON=C:\Users\79615\AppData\Local\Programs\Python\Python310\python.exe

if exist "%PYTHONW%" (
  start "" "%PYTHONW%" "%SCRIPT_DIR%operator_assist.py"
) else (
  "%PYTHON%" "%SCRIPT_DIR%operator_assist.py"
)
