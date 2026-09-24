# -*- mode: python ; coding: utf-8 -*-
# Build de la app de escritorio para macOS (.app). SE CORRE EN UNA MAC:
# PyInstaller no compila para otro sistema operativo.
#   python3 -m PyInstaller --clean --noconfirm NuevosNegociosAI-mac.spec
# Sale dist/Nuevos Negocios AI.app. La arquitectura es la del Python con el
# que se compila (Apple Silicon -> arm64, Intel -> x86_64).
# Mismo contenido que NuevosNegociosAI.spec (Windows); ver ahi el porque de
# cada paquete. Diferencia: en Mac va en carpeta (onedir) dentro de un BUNDLE,
# que es lo que macOS espera de un .app (onefile + .app esta desaconsejado).
from PyInstaller.utils.hooks import collect_all

import os as _os
if _os.path.getsize("launcher.py") < 1000:
    raise SystemExit("ABORTADO: launcher.py tiene "
                     f"{_os.path.getsize('launcher.py')} bytes; esta vacio o truncado.")

datas, binaries, hiddenimports = [], [], []

for pkg in ("undetected_chromedriver", "selenium", "curl_cffi",
            "uvicorn", "fastapi", "starlette", "lxml"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

hiddenimports += [
    "uvicorn.loops.auto", "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on", "uvicorn.lifespan.off",
    "uvicorn.logging",
]

datas += [
    ("NN AI - Verticales MELI.csv", "."),
    ("categorias_ar.json", "."),
    ("categorias_mx.json", "."),
    ("categorias_uy.json", "."),
    ("categorias_br.json", "."),
    ("arbol_ar.json", "."),
    ("../htmlMvpNuevosNegociosAI.html", "."),   # la web esta en Recursos/
]

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pandas", "openpyxl", "matplotlib", "tkinter", "PyQt5", "PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NuevosNegociosAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
    icon="nuevos_negocios_ai_icono_mac.icns",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="NuevosNegociosAI",
)

app = BUNDLE(
    coll,
    name="Nuevos Negocios AI.app",
    icon="nuevos_negocios_ai_icono_mac.icns",
    bundle_identifier="ar.com.bidcom.nuevosnegociosai",
    info_plist={
        "CFBundleDisplayName": "Nuevos Negocios AI",
        "CFBundleShortVersionString": "1.0",
        "NSHighResolutionCapable": True,
        # Sin icono propio en el Dock: la app es un backend que abre el
        # navegador; la ventana visible es la del navegador del usuario.
        "LSUIElement": True,
    },
)
