@echo off
REM Mantiene la app SIEMPRE online: levanta backend + tunel y los reinicia solos
REM si se caen. Escribe el link publico actual en el Escritorio ("LINK DE LA APP.txt").
REM Dejala corriendo (podes minimizar la ventana). Para que arranque sola al prender
REM la PC, ver INTEGRACION.md (un paso de una sola vez).
cd /d "%~dp0"
echo Manteniendo la app online... (NO cierres esta ventana)
echo El link para compartir aparece en el Escritorio: "LINK DE LA APP.txt"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0mantener_online.ps1"
