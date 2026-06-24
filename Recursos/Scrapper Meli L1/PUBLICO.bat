@echo off
REM ============================================================
REM  Levanta la app COMPLETA y la publica en internet con 1 clic.
REM  - Backend FastAPI (sirve tambien la web) en el puerto 8000.
REM  - Tunel Cloudflare: te da una URL publica https://XXXX.trycloudflare.com
REM  Mientras estas dos ventanas esten abiertas, cualquiera puede usar la app.
REM ============================================================
cd /d "%~dp0"

echo Abriendo el backend (puerto 8000)...
start "Backend Meli" cmd /k py -m uvicorn api:app --host 0.0.0.0 --port 8000

echo Esperando a que el backend levante...
timeout /t 4 >nul

echo Abriendo el tunel Cloudflare...
start "Tunel Cloudflare" cmd /k cloudflared.exe tunnel --url http://localhost:8000 --no-autoupdate

echo.
echo ============================================================
echo  Se abrieron DOS ventanas: "Backend Meli" y "Tunel Cloudflare".
echo  En la ventana "Tunel Cloudflare" vas a ver una linea como:
echo     https://XXXX-XXXX-XXXX.trycloudflare.com
echo  ESA es la URL que compartis. Abrila y ya funciona la app.
echo.
echo  OJO: la URL cambia cada vez que reabris el tunel (version gratis).
echo  Para una URL fija ver INTEGRACION.md (named tunnel + dominio).
echo ============================================================
pause
