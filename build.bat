@echo off
echo =================================================================
echo  This script will build the server.exe file.
echo  It will create a temporary Python virtual environment.
echo =================================================================
echo.

REM Define the explicit path to the Python executable
set PYTHON_EXE="C:\Users\narjiang\AppData\Local\Python\pythoncore-3.14-64\python.exe"

REM Check if Python executable exists
if not exist %PYTHON_EXE% (
    echo Error: Python executable not found at %PYTHON_EXE%
    echo Please ensure the path is correct.
    pause
    exit /b 1
)

set VENV_DIR=.\venv_build
set EXE_NAME=server

echo Creating virtual environment in %VENV_DIR%...
%PYTHON_EXE% -m venv %VENV_DIR%
if %errorlevel% neq 0 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
)

echo Activating virtual environment...
call %VENV_DIR%\Scripts\activate.bat

echo Installing required packages (pyinstaller, flask, requests)...
pip install pyinstaller flask requests
if %errorlevel% neq 0 (
    echo Failed to install packages.
    pause
    exit /b 1
)

echo.
echo =================================================================
echo  Starting the build process with PyInstaller...
echo =================================================================
echo.

pyinstaller --name %EXE_NAME% ^
            --onefile ^
            --add-data "%~dp0Portal.html;." ^
            server.py

if %errorlevel% neq 0 (
    echo PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo =================================================================
echo  Build successful!
echo  You can find the executable at: dist\%EXE_NAME%.exe
echo =================================================================
echo.

REM Deactivate and clean up
deactivate
rmdir /s /q %VENV_DIR%
rmdir /s /q build
del %EXE_NAME%.spec

echo Cleanup complete.
pause