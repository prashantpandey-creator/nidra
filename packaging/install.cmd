@echo off
REM Nidra installer - Windows. Never asks for administrator rights.
setlocal enabledelayedexpansion

set "HERE=%~dp0"
set "APP=%USERPROFILE%\.nidra-app"
set "BIN=%USERPROFILE%\.local\bin"

echo.
echo Installing Nidra
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo   Nidra needs Python 3.9 or newer, and python was not found.
  echo   Install it from python.org ^(tick "Add to PATH"^), then run this again.
  exit /b 1
)
for /f "delims=" %%v in ('python -c "import sys; print('%%d.%%d' %% sys.version_info[:2])"') do set "PYV=%%v"
echo   found python !PYV!

if exist "%APP%" rmdir /s /q "%APP%"
mkdir "%APP%" 2>nul
if not exist "%BIN%" mkdir "%BIN%" 2>nul
xcopy /e /i /q "%HERE%runtime\nidra" "%APP%\nidra" >nul
echo   copied Nidra to %APP%

> "%BIN%\nidra.cmd" echo @echo off
>> "%BIN%\nidra.cmd" echo python -c "import sys; sys.path.insert(0, r'%APP%'); from nidra.cli import main; sys.exit(main())" %%*
echo   created the 'nidra' command in %BIN%

echo %PATH% | find /i "%BIN%" >nul
if errorlevel 1 (
  setx PATH "%BIN%;%PATH%" >nul
  echo   added %BIN% to your PATH
  echo.
  echo   Close this window, open a NEW terminal, then run:  nidra demo
) else (
  echo.
  echo   Done. Try it now:  nidra demo
)
echo.
endlocal
