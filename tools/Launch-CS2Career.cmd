@echo off
setlocal
cd /d "%~dp0"
if not exist "runtime-temp" mkdir "runtime-temp"
set "TEMP=%~dp0runtime-temp"
set "TMP=%~dp0runtime-temp"
start "" "CS2Career.exe"
endlocal
