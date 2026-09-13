@echo off
setlocal
cd /d "%~dp0"

REM 1. Detect Python binary
set PYTHON_CMD=

if exist "%~dp0.venv\Scripts\python.exe" (
    set PYTHON_CMD="%~dp0.venv\Scripts\python.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
    set PYTHON_CMD="%~dp0venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        where py >nul 2>nul
        if errorlevel 1 (
            where python3 >nul 2>nul
            if errorlevel 1 (
                goto :no_python
            ) else (
                set PYTHON_CMD=python3
            )
        ) else (
            set PYTHON_CMD=py -3
        )
    ) else (
        set PYTHON_CMD=python
    )
)

if not defined PYTHON_CMD goto :no_python

REM 2. Check dependencies (fast import check)
%PYTHON_CMD% -c "import PyQt6, sympy, matplotlib, numpy" >nul 2>nul
if errorlevel 1 (
    echo [INFO] Missing required packages detected.
    echo Installing dependencies from requirements.txt...
    %PYTHON_CMD% -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to install required packages.
        echo Please check your internet connection or run:
        echo   pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo [SUCCESS] Dependencies installed successfully!
)

REM 3. Launch Application
%PYTHON_CMD% "%~dp0main.py" %*
exit /b %ERRORLEVEL%

:no_python
echo [ERROR] Python 3 was not found in your system PATH.
echo Please install Python 3.10+ from https://www.python.org or the Microsoft Store.
pause
exit /b 1
