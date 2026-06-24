@echo off
REM Expone el backend local (puerto 8000) a internet con Cloudflare Tunnel.
REM Imprime una URL publica https://XXXX.trycloudflare.com que tu web puede usar.
REM (El backend tiene que estar corriendo: ejecuta start.bat primero.)
cd /d "%~dp0"

if not exist cloudflared.exe (
  echo No se encontro cloudflared.exe en esta carpeta.
  echo Descargalo de https://github.com/cloudflare/cloudflared/releases
  echo y copialo a esta carpeta.
  pause
  exit /b 1
)

echo Abriendo tunel Cloudflare hacia http://localhost:8000 ...
echo Copia la URL https://XXXX.trycloudflare.com que aparezca abajo.
echo Esa es la URL que pones en la web (ver INTEGRACION.md).
echo.
cloudflared.exe tunnel --url http://localhost:8000
pause
