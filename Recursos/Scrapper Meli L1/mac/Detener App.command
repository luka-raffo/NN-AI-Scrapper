#!/bin/bash
# macOS: detiene la app (backend en el puerto 8000), sea el .app o el codigo.
# Manda SIGTERM (no -9): uvicorn apaga ordenado y el hook de shutdown cierra
# los Chrome del motor, asi no quedan ventanas de Chrome huerfanas.
PIDS=$(lsof -ti tcp:8000 -sTCP:LISTEN 2>/dev/null)
if [ -z "$PIDS" ]; then
    echo "La app no estaba corriendo."
else
    kill -TERM $PIDS
    for _ in $(seq 1 20); do
        lsof -ti tcp:8000 -sTCP:LISTEN >/dev/null 2>&1 || break
        sleep 0.5
    done
    if lsof -ti tcp:8000 -sTCP:LISTEN >/dev/null 2>&1; then
        kill -9 $(lsof -ti tcp:8000 -sTCP:LISTEN) 2>/dev/null
    fi
    echo "La app quedo detenida."
fi
sleep 2
