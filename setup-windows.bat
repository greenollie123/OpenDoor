@echo off
setlocal enabledelayedexpansion

set "DIR=%~dp0"
if "%DIR:~-1%"=="\" set "DIR=%DIR:~0,-1%"

echo Project directory: "%DIR%"

REM 1. Create virtual environment if it doesn't exist
if not exist "%DIR%\venv" (
    echo.
    echo [1/3] Creating virtual environment...
    python -m venv "%DIR%\venv"
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment. Is Python installed and added to PATH?
        pause
        exit /b 1
    )
) else (
    echo [1/3] Virtual environment already exists.
)

REM 2. Install/Upgrade requirements
echo.
echo [2/3] Installing/upgrading requirements...
"%DIR%\venv\Scripts\pip" install --only-binary :all: "litellm>=1.60.0"
"%DIR%\venv\Scripts\pip" install -r "%DIR%\requirements.txt"
if errorlevel 1 (
    echo WARNING: Pip installation encountered errors. Please check your internet connection or requirements.txt
)

REM 3. Add to user PATH
echo.
echo [3/3] Setting up PATH environment variable...
powershell -NoProfile -Command "$p = [System.Environment]::GetEnvironmentVariable('PATH', 'User'); if (-not $p.Split(';').Contains('%DIR%\terminal')) { [System.Environment]::SetEnvironmentVariable('PATH', $p + ';%DIR%\terminal', 'User'); Write-Host 'Added to PATH successfully!' -ForegroundColor Green } else { Write-Host 'Already in PATH.' -ForegroundColor Yellow }"

REM 4. Launch configuration wizard
echo.
echo [4/4] Starting configuration wizard...
if exist "%DIR%\venv\Scripts\python.exe" (
    "%DIR%\venv\Scripts\python.exe" "%DIR%\terminal\setup.py"
) else (
    python "%DIR%\terminal\setup.py"
)

echo.
echo OpenDoor setup complete.
echo Please restart your terminal to apply PATH changes.
echo.
set /p "RUN_NOW=Would you like to run 'opendoor launch' now? (Y/n): "
if /i "%RUN_NOW%"=="y" (
    "%DIR%\terminal\opendoor.bat" launch
) else if "%RUN_NOW%"=="" (
    "%DIR%\terminal\opendoor.bat" launch
)
