@echo off
setlocal
title Self-Healing Network - Launcher
set "ROOT=%~dp0"
set "PROJECT=network_repair_working"

echo ============================================
echo   Self-Healing Network - starting everything
echo ============================================
echo.

if not exist "%ROOT%ai-service\.venv\Scripts\python.exe" (
  echo ERROR: AI Python environment was not found.
  echo Expected: "%ROOT%ai-service\.venv\Scripts\python.exe"
  echo Create the environment and install ai-service\requirements.txt first.
  goto :failed
)
if not exist "%ROOT%network\.venv\Scripts\python.exe" (
  echo ERROR: Backend Python environment was not found.
  echo Expected: "%ROOT%network\.venv\Scripts\python.exe"
  echo Create the environment and install network\requirements.txt first.
  goto :failed
)
if not exist "%ROOT%dashboard\node_modules\.bin\vite.cmd" (
  echo ERROR: Dashboard dependencies were not found.
  echo Run "npm install" from "%ROOT%dashboard" first.
  goto :failed
)
where npm >nul 2>&1
if errorlevel 1 (
  echo ERROR: npm was not found. Install Node.js and reopen this window.
  goto :failed
)

echo Checking that the application ports are available...
netstat -ano -p tcp | findstr /R /C:":8000 .*LISTENING" >nul
if not errorlevel 1 (
  echo ERROR: Port 8000 is already in use. Stop the existing service before starting this project.
  netstat -ano -p tcp | findstr /R /C:":8000 .*LISTENING"
  goto :failed
)
netstat -ano -p tcp | findstr /R /C:":8080 .*LISTENING" >nul
if not errorlevel 1 (
  echo ERROR: Port 8080 is already in use. Stop the existing service before starting this project.
  netstat -ano -p tcp | findstr /R /C:":8080 .*LISTENING"
  goto :failed
)
netstat -ano -p tcp | findstr /R /C:":5173 .*LISTENING" >nul
if not errorlevel 1 (
  echo ERROR: Port 5173 is already in use. Stop the existing service before starting this project.
  netstat -ano -p tcp | findstr /R /C:":5173 .*LISTENING"
  goto :failed
)

echo [1/4] Checking MongoDB...
powershell -NoProfile -Command "try { $s = Get-Service -Name '*mongo*' -ErrorAction Stop | Select-Object -First 1; if ($s.Status -ne 'Running') { Start-Service -InputObject $s -ErrorAction Stop }; $c = New-Object System.Net.Sockets.TcpClient; $c.Connect('127.0.0.1',27017); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
  echo ERROR: MongoDB is unavailable on port 27017.
  echo Start the MongoDB service from services.msc, then run this file again.
  goto :failed
)
echo   MongoDB is ready.

echo [2/4] Starting AI service on port 8000...
start "SHN AI - %PROJECT%" /D "%ROOT%ai-service" cmd /k ".venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000"
set "ATTEMPTS=0"
:wait_ai
curl.exe -fsS http://127.0.0.1:8000/health >nul 2>&1
if not errorlevel 1 goto :ai_ready
set /a ATTEMPTS+=1
if %ATTEMPTS% GEQ 30 (
  echo ERROR: AI service did not become ready within 30 seconds.
  echo Check the "SHN AI - %PROJECT%" window for the startup error.
  goto :failed
)
timeout /t 1 /nobreak >nul
goto :wait_ai
:ai_ready
echo   AI service is ready.

echo [3/4] Starting Python backend on port 8080...
start "SHN Backend - %PROJECT%" /D "%ROOT%network" cmd /k ".venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8080"
set "ATTEMPTS=0"
:wait_backend
curl.exe -fsS http://127.0.0.1:8080/api/health >nul 2>&1
if not errorlevel 1 goto :backend_ready
set /a ATTEMPTS+=1
if %ATTEMPTS% GEQ 45 (
  echo ERROR: Backend did not become ready within 45 seconds.
  echo Check the "SHN Backend - %PROJECT%" window for the startup error.
  goto :failed
)
timeout /t 1 /nobreak >nul
goto :wait_backend
:backend_ready
echo   Backend is ready.

echo [4/4] Starting dashboard on port 5173...
start "SHN Dashboard - %PROJECT%" /D "%ROOT%dashboard" cmd /k "npm run dev -- --host 0.0.0.0"
set "ATTEMPTS=0"
:wait_dashboard
curl.exe -fsS http://127.0.0.1:5173/ >nul 2>&1
if not errorlevel 1 goto :dashboard_ready
set /a ATTEMPTS+=1
if %ATTEMPTS% GEQ 30 (
  echo ERROR: Dashboard did not become ready within 30 seconds.
  echo Check the "SHN Dashboard - %PROJECT%" window for the startup error.
  goto :failed
)
timeout /t 1 /nobreak >nul
goto :wait_dashboard
:dashboard_ready
start "" http://127.0.0.1:5173
echo.
echo Everything is running!
echo Database: MongoDB at mongodb://localhost:27017 (database: selfhealing)
echo To stop these services, double-click stop-all.bat.
echo.
pause
exit /b 0

:failed
echo.
echo Startup stopped. Fix the issue shown above and run start-all.bat again.
pause
exit /b 1
