@echo off
setlocal
cd /d "%~dp0"
echo ======================================
echo H-STAFF - FIRST TIME PC SETUP
echo ======================================
node -v
if errorlevel 1 (
  echo Node.js 22 or newer is required. Install it from https://nodejs.org/
  pause
  exit /b 1
)
if not exist "server\.env" (
  copy "server\.env.example" "server\.env" >nul
  echo Created server\.env for local development OTP.
)
echo Installing frontend dependencies...
call npm install
if errorlevel 1 goto failed
echo Installing backend dependencies...
call npm install --prefix server
if errorlevel 1 goto failed
echo.
echo Setup complete. Run START-HSTAFF.bat to launch H-Staff.
pause
exit /b 0
:failed
echo Setup failed. Check your internet connection and Node.js installation.
pause
exit /b 1
