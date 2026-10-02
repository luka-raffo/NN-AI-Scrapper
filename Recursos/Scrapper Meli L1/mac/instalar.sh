#!/bin/bash
# ============================================================
#  Instalador de "Nuevos Negocios AI" para macOS. Se usa pegando en Terminal:
#    curl -fsSL https://github.com/luka-raffo/NN-AI-Scrapper/releases/download/mac-latest/instalar.sh | bash
#  Por que asi y no pasando el .zip: el .app no esta firmado con una cuenta de
#  desarrollador de Apple. Lo que se baja con el navegador (o llega por
#  AirDrop/Slack/mail) queda "en cuarentena", y aunque se habilite en
#  Seguridad, macOS sigue bloqueando el Python que va adentro y la app tira
#  error al arrancar. Lo que baja curl no queda en cuarentena.
#  Sirve tambien para ACTUALIZAR: correrlo de nuevo instala la ultima version.
# ============================================================
set -euo pipefail

APP_NAME="Nuevos Negocios AI.app"
URL="https://github.com/luka-raffo/NN-AI-Scrapper/releases/download/mac-latest/NuevosNegociosAI-mac-arm64.zip"

echo "== Instalando Nuevos Negocios AI =="

# 1. Mac compatible: el build es para Apple Silicon (M1/M2/M3/M4).
if [ "$(sysctl -n hw.optional.arm64 2>/dev/null || echo 0)" != "1" ]; then
    echo "Esta Mac tiene procesador Intel; esta version es solo para Macs con chip Apple (M1 a M4)."
    exit 1
fi

# 2. Chrome: la app lo usa para leer Mercado Libre.
if [ ! -d "/Applications/Google Chrome.app" ] && [ ! -d "$HOME/Applications/Google Chrome.app" ]; then
    echo "Falta Google Chrome. Instalalo desde https://www.google.com/chrome/ y volve a correr este comando."
    exit 1
fi

# 3. Si ya estaba abierta (actualizacion), cerrarla primero.
PIDS=$(lsof -ti tcp:8000 -sTCP:LISTEN 2>/dev/null || true)
if [ -n "$PIDS" ]; then
    echo "Cerrando la version abierta..."
    kill -TERM $PIDS 2>/dev/null || true
    sleep 3
fi

# 4. Descargar e instalar.
DEST="/Applications"
[ -w "$DEST" ] || { DEST="$HOME/Applications"; mkdir -p "$DEST"; }
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
echo "Descargando (unos 40 MB)..."
curl -fL --progress-bar -o "$TMP/app.zip" "$URL"
rm -rf "$DEST/$APP_NAME"
ditto -x -k "$TMP/app.zip" "$DEST"
xattr -cr "$DEST/$APP_NAME" 2>/dev/null || true   # por las dudas

# 5. Acceso directo para cerrarla (la app no tiene ventana propia ni icono en el Dock).
STOP="$HOME/Desktop/Detener Nuevos Negocios AI.command"
cat > "$STOP" <<'EOS'
#!/bin/bash
# Cierra Nuevos Negocios AI (y los Chrome que usa por detras).
PIDS=$(lsof -ti tcp:8000 -sTCP:LISTEN 2>/dev/null)
if [ -z "$PIDS" ]; then
    echo "La app no estaba abierta."
else
    kill -TERM $PIDS
    for _ in $(seq 1 20); do
        lsof -ti tcp:8000 -sTCP:LISTEN >/dev/null 2>&1 || break
        sleep 0.5
    done
    lsof -ti tcp:8000 -sTCP:LISTEN >/dev/null 2>&1 && kill -9 $(lsof -ti tcp:8000 -sTCP:LISTEN)
    echo "La app quedo cerrada. Ya podes cerrar esta ventana."
fi
EOS
chmod +x "$STOP"

echo
echo "Listo. Instalada en: $DEST/$APP_NAME"
echo "Para abrirla: Launchpad o Aplicaciones -> 'Nuevos Negocios AI' (se abre en el navegador)."
echo "Para cerrarla: doble clic en 'Detener Nuevos Negocios AI' en el Escritorio."
echo "Abriendola ahora..."
open "$DEST/$APP_NAME"
