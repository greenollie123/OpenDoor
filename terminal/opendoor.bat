@echo off
REM Get the directory of this batch file (terminal)
set "CURRENT_DIR=%~dp0"
if "%CURRENT_DIR:~-1%"=="\" set "CURRENT_DIR=%CURRENT_DIR:~0,-1%"

REM Get the root directory (one level up)
for %%i in ("%CURRENT_DIR%\..") do set "ROOT_DIR=%%~fi"

set "PYTHON_EXE=python"
if exist "%ROOT_DIR%\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%ROOT_DIR%\venv\Scripts\python.exe"
)

set "ACTION=%~1"
if "%ACTION%"=="setup" goto :run_setup
if "%ACTION%"=="configure" goto :run_config
if "%ACTION%"=="config" goto :run_config
if "%ACTION%"=="update" goto :run_update
if "%ACTION%"=="launch" goto :launch_server
if "%ACTION%"=="start" goto :launch_server
if "%ACTION%"=="run" goto :launch_server
if "%ACTION%"=="server" goto :launch_server

REM Run terminal client if not matching launch actions
"%PYTHON_EXE%" "%CURRENT_DIR%\terminal.py" %*
goto :eof

:run_setup
"%PYTHON_EXE%" "%CURRENT_DIR%\setup.py" %*
goto :eof

:run_config
"%PYTHON_EXE%" "%CURRENT_DIR%\config.py" %*
goto :eof

:run_update
"%PYTHON_EXE%" "%CURRENT_DIR%\update.py" %*
goto :eof

:launch_server
"%PYTHON_EXE%" "%ROOT_DIR%\main.py" %*
