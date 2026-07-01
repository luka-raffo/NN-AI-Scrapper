@echo off
REM ============================================================
REM  Version SIN ventana visible de start.bat, pensada para ser
REM  lanzada oculta desde "Iniciar App.vbs" (nunca a doble clic
REM  directo: si algo falla, no se ve nada). Deja el detalle en
REM  app.log. Si hay problemas, corre start.bat para ver el error.
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
set "LOG=%~dp0app.log"
echo ==== %date% %time% ==== > "%LOG%"

set "PYEXE="
where py >nul 2>nul
if !errorlevel! equ 0 set "PYEXE=py"

if not defined PYEXE (
    where python >nul 2>nul
    if !errorlevel! equ 0 set "PYEXE=python"
)

if not defined PYEXE (
    echo No se encontro Python instalado. >> "%LOG%"
    exit /b 1
)

echo Usando %PYEXE% >> "%LOG%"
!PYEXE! -m pip install -q -r requirements.txt >> "%LOG%" 2>&1
if !errorlevel! neq 0 (
    echo Fallo pip install. >> "%LOG%"
    exit /b 1
)

echo Iniciando uvicorn... >> "%LOG%"
!PYEXE! -m uvicorn api:app --host 0.0.0.0 --port 8000 >> "%LOG%" 2>&1
