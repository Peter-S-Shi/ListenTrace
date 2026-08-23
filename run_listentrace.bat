@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe"
set "VENV_PYTHONW=%SCRIPT_DIR%.venv\Scripts\pythonw.exe"

if not exist "%VENV_PYTHON%" (
    echo [ListenTrace] Virtual environment not found at "%SCRIPT_DIR%.venv"
    echo.
    echo Run setup first, from this folder:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -e ".[dev]"
    echo.
    pause
    exit /b 1
)

start "" "%VENV_PYTHONW%" -m listentrace.ui.app
