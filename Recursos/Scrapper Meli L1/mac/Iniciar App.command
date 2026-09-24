#!/bin/bash
# ============================================================
#  macOS: levanta la app desde el codigo (sin compilar el .app).
#  Doble clic en Finder. La 1a vez crea un entorno de Python en
#  .venv-mac e instala dependencias (tarda un par de minutos);
#  las siguientes arranca directo. Abre el navegador solo.
#  Requisitos: Python 3.10+ (python.org) y Google Chrome.
# ============================================================
cd "$(dirname "$0")/.." || exit 1

if ! command -v python3 >/dev/null 2>&1; then
    echo "No se encontro Python 3. Instalalo desde https://www.python.org/downloads/macos/ y volve a abrir este archivo."
    read -r -p "Enter para cerrar..."
    exit 1
fi
if [ ! -d "/Applications/Google Chrome.app" ] && [ ! -d "$HOME/Applications/Google Chrome.app" ]; then
    echo "No se encontro Google Chrome. Instalalo desde https://www.google.com/chrome/ (la app lo usa para leer Mercado Libre)."
    read -r -p "Enter para cerrar..."
    exit 1
fi

if [ ! -x ".venv-mac/bin/python" ]; then
    echo "Primera vez: creando entorno de Python..."
    python3 -m venv .venv-mac || { read -r -p "Fallo crear el entorno. Enter para cerrar..."; exit 1; }
fi
echo "Verificando dependencias (rapido si ya estan instaladas)..."
.venv-mac/bin/python -m pip install -q --upgrade pip
.venv-mac/bin/python -m pip install -q -r requirements.txt || { read -r -p "Fallo instalar dependencias. Enter para cerrar..."; exit 1; }

echo
echo "Iniciando backend + web en http://127.0.0.1:8000"
echo "El navegador se abre solo. Deja esta ventana abierta (Ctrl+C o cerrarla para detener)."
echo
exec .venv-mac/bin/python launcher.py
