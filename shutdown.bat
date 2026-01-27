@echo off
setlocal
echo ============================================
echo Shutting down SciSAI App Services (Port-based)
echo ============================================

:: Helper Loop to find and kill PIDs on specific ports

:: 1. Backend (Port 8001)
echo [1/2] Stopping Backend on Port 8001...
set "found_backend="
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001" ^| findstr "LISTENING"') do (
    set found_backend=1
    echo Found PID %%a listening on 8001. Killing...
    taskkill /F /PID %%a >nul 2>&1
)
if not defined found_backend (
    echo No active process found on port 8001.
) else (
    echo Backend process terminated.
)

:: 2. Frontend (Port 5173)
echo [2/2] Stopping Frontend on Port 5173...
set "found_frontend="
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173" ^| findstr "LISTENING"') do (
    set found_frontend=1
    echo Found PID %%a listening on 5173. Killing...
    taskkill /F /PID %%a >nul 2>&1
)
if not defined found_frontend (
    echo No active process found on port 5173.
) else (
    echo Frontend process terminated.
)

echo.
echo ============================================
echo Shutdown complete.
echo Note: If console windows remain open, you can safely close them.
echo Grobid Server is still running.
echo ============================================
pause
