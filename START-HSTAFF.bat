@echo off
setlocal
cd /d "%~dp0"
if not exist "node_modules" (
  echo Run SETUP-PC.bat first.
  pause
  exit /b 1
)
if not exist "server\node_modules" (
  echo Run SETUP-PC.bat first.
  pause
  exit /b 1
)
if not exist "server\.env" (
  copy "server\.env.example" "server\.env" >nul
  echo Created server\.env for local development OTP.
)
start "H-Staff API" /D "%~dp0" cmd /k "npm run dev --prefix server"
start "H-Staff Frontend" /D "%~dp0" cmd /k "npm run dev"
timeout /t 4 /nobreak >nul
start "" "http://localhost:5173"
echo H-Staff is starting. Keep both terminal windows open.
