@echo off
REM ============================================================
REM  Windows no permite ponerle un icono propio a un .bat/.vbs
REM  (siempre muestra el icono generico). Este script crea, una
REM  sola vez, un acceso directo "Iniciar App.lnk" en esta misma
REM  carpeta que apunta a "Iniciar App.vbs" (lanzador SIN ventana
REM  de CMD) y usa el icono de la app.
REM  A partir de ahi, usa ESE acceso directo para el doble clic:
REM  no se ve ninguna consola y siempre termina abriendo el
REM  navegador con la app.
REM ============================================================
set "HERE=%~dp0"
cd /d "%HERE%"

if not exist "nuevos_negocios_ai_icono_windows.ico" (
    echo No se encontro "nuevos_negocios_ai_icono_windows.ico" en esta carpeta.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $lnk = $ws.CreateShortcut('%HERE%Iniciar App.lnk'); $lnk.TargetPath = '%HERE%Iniciar App.vbs'; $lnk.WorkingDirectory = '%HERE%'; $lnk.IconLocation = '%HERE%nuevos_negocios_ai_icono_windows.ico,0'; $lnk.Description = 'Iniciar la app Mas Vendidos MELI (backend + web)'; $lnk.Save()"

if not %errorlevel%==0 (
    echo.
    echo No se pudo crear el acceso directo. Revisa el error de arriba.
    pause
    exit /b 1
)

echo.
echo Listo: se creo "Iniciar App.lnk" en esta carpeta, con el icono de la app.
echo A partir de ahora, hace doble clic en ESE acceso directo para abrir la app.
pause
