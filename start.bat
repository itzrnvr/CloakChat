@echo off
setlocal EnableDelayedExpansion

echo Starting CloakChat
echo ========================
echo.

set BACKEND_PORT=8012
set FRONTEND_PORT=5173
set PROJECT_DIR=%~dp0

REM Check prerequisites
echo Checking prerequisites...

python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Please install Python 3.12+
    pause
    exit /b 1
)

if not exist "%PROJECT_DIR%.venv" (
    echo Virtual environment not found. Run: python -m venv .venv
    pause
    exit /b 1
)

bun --version >nul 2>&1
if errorlevel 1 (
    echo Bun not found. Install from https://bun.sh
    pause
    exit /b 1
)

echo Prerequisites OK
echo.

REM Kill previous CloakChat instances
echo Stopping previous CloakChat instances...

REM Kill frontend window if still open
taskkill /FI "WINDOWTITLE eq CloakChat Frontend" /F >nul 2>&1

REM Kill processes on backend port
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%BACKEND_PORT%') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM Kill processes on frontend port
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%FRONTEND_PORT%') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM Kill any lingering python/bun processes from CloakChat
taskkill /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq CloakChat*" /F >nul 2>&1
taskkill /FI "IMAGENAME eq bun.exe" /FI "WINDOWTITLE eq CloakChat*" /F >nul 2>&1

REM Brief pause to let ports release
timeout /t 1 /nobreak >nul
echo Done.

REM Start Frontend in new window (background)
echo Starting frontend server...
cd /d "%PROJECT_DIR%\frontend"
start "CloakChat Frontend" cmd /c "bun run dev"
echo Frontend started in new window
echo App: http://localhost:%FRONTEND_PORT%
echo.

REM Wait a moment for frontend to initialize
timeout /t 2 /nobreak >nul

REM Start Backend in THIS terminal (foreground, all logs visible)
echo ========================
echo BACKEND LOGS START BELOW
echo ========================
echo.

cd /d "%PROJECT_DIR%"
call .venv\Scripts\activate.bat
set PYTHONPATH=%PROJECT_DIR%;%PYTHONPATH%
python backend\main.py

REM Backend exited - cleanup frontend
echo.
echo ========================
echo Backend stopped. Shutting down frontend...
echo ========================
taskkill /FI "WINDOWTITLE eq CloakChat Frontend" /F >nul 2>&1

echo.
echo All servers stopped.
pause
