@echo off
setlocal
cd /d "%~dp0"
call npm run seed --prefix server
if errorlevel 1 echo Demo data could not be loaded. Check the backend dependencies.
pause
