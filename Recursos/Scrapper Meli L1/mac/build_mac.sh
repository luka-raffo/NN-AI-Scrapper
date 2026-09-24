#!/bin/bash
# ============================================================
#  Compila "Nuevos Negocios AI.app" (correr EN UNA MAC):
#     bash mac/build_mac.sh
#  Sale en dist/ y un .zip listo para pasar a otra Mac.
#  El .app queda para la arquitectura de esta Mac (Apple Silicon o Intel).
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m venv .venv-build
.venv-build/bin/python -m pip install -q --upgrade pip
.venv-build/bin/python -m pip install -q -r requirements.txt pyinstaller

rm -rf build "dist/Nuevos Negocios AI.app" dist/NuevosNegociosAI
.venv-build/bin/python -m PyInstaller --clean --noconfirm NuevosNegociosAI-mac.spec

APP="dist/Nuevos Negocios AI.app"
# Chequeos post-build (ver NuevosNegociosAI.spec: lxml se cae del build si no
# se colecta explicito, y sin el HTML la app arranca sin web).
N_LXML=$(find "$APP" -path "*lxml*" -name "etree*.so" | wc -l | tr -d ' ')
N_HTML=$(find "$APP" -name "htmlMvpNuevosNegociosAI.html" | wc -l | tr -d ' ')
if [ "$N_LXML" -lt 1 ] || [ "$N_HTML" -lt 1 ]; then
    echo "ABORTADO: al .app le falta lxml ($N_LXML) o la web ($N_HTML)."
    exit 1
fi

# Firma ad-hoc de todo el bundle (Apple Silicon no ejecuta binarios sin firma).
codesign --force --deep --sign - "$APP"

ditto -c -k --keepParent "$APP" "dist/NuevosNegociosAI-mac-$(uname -m).zip"
echo
echo "Listo: $APP"
echo "Zip para compartir: dist/NuevosNegociosAI-mac-$(uname -m).zip"
