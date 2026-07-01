@echo off
setlocal enabledelayedexpansion
REM ============================================================
REM  Un solo doble clic: instala dependencias (si faltan), levanta
REM  el backend FastAPI (que tambien sirve la web) y abre el
REM  navegador solo. Uso 100%% local, sin tunel ni internet.
REM ============================================================
cd /d "%~dp0"

set "PYEXE="
where py >nul 2>nul
if !errorlevel! equ 0 set "PYEXE=py"

if not defined PYEXE (
    where python >nul 2>nul
    if !errorlevel! equ 0 set "PYEXE=python"
)

if not defined PYEXE (
    echo No se encontro Python instalado.
    echo Instalalo desde https://www.python.org/downloads/ ^(tildar "Add to PATH"^) y volve a ejecutar este archivo.
    pause
    exit /b 1
)

echo Verificando dependencias ^(rapido si ya estan instaladas^)...
!PYEXE! -m pip install -q -r requirements.txt
if !errorlevel! neq 0 (
    echo.
    echo Fallo la instalacion de dependencias. Revisa el error de arriba.
    pause
    exit /b 1
)

REM Abre el navegador en la web (front+back en una sola URL) unos segundos
REM despues, dando tiempo a que uvicorn levante.
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8000/"

echo.
echo Iniciando backend + web en http://127.0.0.1:8000
echo El navegador se abre solo. Deja esta ventana abierta (Ctrl+C para detener).
echo.
!PYEXE! -m uvicorn api:app --host 0.0.0.0 --port 8000
pause
