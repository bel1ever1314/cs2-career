@echo off
setlocal
rem Supply CS2CAREER_GODOT or place Godot.exe in the source tree tools/godot folder.
if not defined CS2CAREER_GODOT set "CS2CAREER_GODOT=%~dp0..\..\tools\godot\Godot.exe"
if not exist "%CS2CAREER_GODOT%" (
    echo Set CS2CAREER_GODOT to your Godot 4 executable.
    pause
    exit /b 1
)
if not exist "%~dp0runtime" mkdir "%~dp0runtime"
start "" "%CS2CAREER_GODOT%" --path "%~dp0." --log-file "%~dp0runtime\godot.log"
endlocal
exit /b 0
