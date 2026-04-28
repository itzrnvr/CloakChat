@echo off
setlocal EnableDelayedExpansion

echo Starting CloakChat
echo ========================
echo.

set BACKEND_PORT=8012
set FRONTEND_PORT=5173
set PROJECT_DIR=%~dp0
set FRONTEND_PID=

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

call :kill_port %BACKEND_PORT%
if errorlevel 1 goto :startup_failed
call :kill_port %FRONTEND_PORT%
if errorlevel 1 goto :startup_failed

REM Kill any lingering python/bun processes from CloakChat
taskkill /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq CloakChat*" >nul 2>&1
taskkill /FI "IMAGENAME eq bun.exe" /FI "WINDOWTITLE eq CloakChat*" >nul 2>&1

call :wait_port_free %BACKEND_PORT%
if errorlevel 1 goto :startup_failed
call :wait_port_free %FRONTEND_PORT%
if errorlevel 1 goto :startup_failed
echo Done.

REM Start Frontend in background (same window, no separate terminal)
echo Starting frontend server...
cd /d "%PROJECT_DIR%\frontend"
start /b "" cmd /c "bun run dev" >nul 2>&1
REM Give cmd /c a moment to spawn bun, then capture bun's PID from the port
timeout /t 2 /nobreak >nul
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /R /C:":%FRONTEND_PORT% .*LISTENING"') do (
    set FRONTEND_PID=%%p
)
if defined FRONTEND_PID (
    echo Frontend started (PID: %FRONTEND_PID%)
) else (
    echo Frontend starting...
)
echo App: http://localhost:%FRONTEND_PORT%
echo.

REM Start Backend in THIS terminal (foreground, all logs visible)
echo ========================
echo BACKEND LOGS START BELOW
echo ========================
echo.
echo Press Ctrl+C to stop both servers.
echo.

cd /d "%PROJECT_DIR%"
call .venv\Scripts\activate.bat
set PYTHONPATH=%PROJECT_DIR%;%PYTHONPATH%
set CLOAKCHAT_RELOAD=0
python backend\main.py

REM Backend exited normally - cleanup frontend

:cleanup
echo.
echo ========================
echo Shutting down CloakChat...
echo ========================

REM Kill frontend by PID if we captured it
if defined FRONTEND_PID (
    taskkill /T /PID %FRONTEND_PID% /F >nul 2>&1
    echo Frontend stopped (PID: %FRONTEND_PID%)
) else (
    REM Fallback: kill by port
    call :kill_port %FRONTEND_PORT%
)

REM Also kill any remaining bun processes on the frontend port
call :kill_port %FRONTEND_PORT%

echo.
echo All servers stopped.
pause
exit /b 0

:startup_failed
echo.
echo Startup failed because a required port could not be released.
echo Close any remaining CloakChat, Python, uvicorn, or Bun windows and run start.bat again.
pause
exit /b 1

:kill_port
set PORT=%~1

REM Try graceful kill first (3 attempts, 1s between)
for /L %%i in (1,1,3) do (
    set FOUND=
    for /f "tokens=5" %%p in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
        set FOUND=1
        echo Graceful kill port %PORT% pid %%p
        taskkill /T /PID %%p >nul 2>&1
    )
    if not defined FOUND exit /b 0
    timeout /t 1 /nobreak >nul
)

REM Fallback force kill if graceful failed
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    echo Force kill port %PORT% pid %%p
    taskkill /T /F /PID %%p >nul 2>&1
    timeout /t 1 /nobreak >nul
)
exit /b 0

:wait_port_free
set PORT=%~1
for /L %%i in (1,1,10) do (
    netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul 2>&1
    if errorlevel 1 exit /b 0
    timeout /t 1 /nobreak >nul
)
echo Port %PORT% is still busy after waiting.
exit /b 1
