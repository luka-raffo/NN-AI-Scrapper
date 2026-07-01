@echo off
REM Mata el proceso que este escuchando en el puerto 8000 (el backend).
setlocal enabledelayedexpansion
for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%p >nul 2>nul
)
exit /b 0
