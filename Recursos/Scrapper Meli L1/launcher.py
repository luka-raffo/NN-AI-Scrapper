# -*- coding: utf-8 -*-
"""
Punto de entrada del ejecutable "Nuevos Negocios AI".
=====================================================
Al abrir el .exe (empaquetado con PyInstaller, ver NuevosNegociosAI.spec):
  1. Levanta el backend FastAPI (que tambien sirve la web) en 127.0.0.1:8000.
  2. Cuando responde /health, abre el navegador con la app.
  3. Si el backend ya estaba corriendo (otra instancia), solo abre el navegador.

Corre en modo "windowed" (sin consola): todo el detalle queda en app.log,
junto al .exe. Para detener la app, cerrar "NuevosNegociosAI.exe" desde el
Administrador de tareas.
"""

import multiprocessing
import os
import socket
import sys
import threading
import time
import webbrowser

HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}/"


def _base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _preparar_salida():
    """En modo windowed, sys.stdout/err son None; muchas libs (uvicorn) fallan al
    escribir. Redirige todo a app.log junto al .exe.

    En macOS el .app puede correr desde una ubicacion de solo lectura (Gatekeeper
    lo "traslada" si se abre desde Descargas): el log va a ~/Library/Logs."""
    if sys.platform == "darwin" and getattr(sys, "frozen", False):
        carpeta = os.path.expanduser("~/Library/Logs/NuevosNegociosAI")
        os.makedirs(carpeta, exist_ok=True)
        log = os.path.join(carpeta, "app.log")
    else:
        log = os.path.join(_base_dir(), "app.log")
    try:
        f = open(log, "a", encoding="utf-8", buffering=1)
        sys.stdout = f
        sys.stderr = f
    except Exception:
        pass
    return log


def _puerto_ocupado():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((HOST, PORT)) == 0


def _abrir_cuando_listo():
    from urllib.request import urlopen
    for _ in range(90):
        try:
            with urlopen(URL + "health", timeout=2) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(1)
    webbrowser.open(URL)


def main():
    log = _preparar_salida()
    print(f"==== Nuevos Negocios AI :: {time.strftime('%Y-%m-%d %H:%M:%S')} ====")
    print(f"log: {log}")

    # Si ya hay backend en el puerto, no levanto otro: solo abro el navegador.
    if _puerto_ocupado():
        print("El backend ya estaba corriendo; abro el navegador.")
        webbrowser.open(URL)
        return

    try:
        import uvicorn
        from api import app
    except Exception:
        import traceback
        traceback.print_exc()
        raise

    threading.Thread(target=_abrir_cuando_listo, daemon=True).start()

    print(f"Levantando backend + web en {URL}")
    # log_config=None: no dejo que uvicorn reconfigure el logging (rompe en
    # modo windowed sin stdout real).
    uvicorn.run(app, host=HOST, port=PORT, log_config=None)


if __name__ == "__main__":
    multiprocessing.freeze_support()  # PyInstaller: evita relanzar el .exe
    main()
