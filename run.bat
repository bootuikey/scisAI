@echo off
echo ============================================
echo Starting SciSAI Environment
echo ============================================

echo [1/3] Starting Grobid Server (Docker)...
:: Check if docker is running first (optional but good)
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Docker is not running! Please start Docker Desktop first.
    pause
    exit /b
)
start "Grobid Server" docker run --rm --name grobid -p 8070:8070 lfoppiano/grobid:0.8.1

echo [2/3] Starting Backend Server...
cd backend
:: Check if virtual environment exists, purely optional heuristic, assuming system python for now as per user context
start "Backend Server" python main.py
cd ..

echo [3/3] Starting Frontend Server...
cd frontend
start "Frontend Server" npm run dev
cd ..

echo ============================================
echo All services are launching!
echo Grobid: http://localhost:8070
echo Backend: http://localhost:8001
echo Frontend: http://localhost:5173 (usually)
echo ============================================
pause
