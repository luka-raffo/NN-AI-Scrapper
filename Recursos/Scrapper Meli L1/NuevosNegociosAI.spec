# -*- mode: python ; coding: utf-8 -*-
# Build del ejecutable "Nuevos Negocios AI" (onefile, sin consola, con icono).
#   py -m PyInstaller --clean --noconfirm NuevosNegociosAI.spec
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []

# Paquetes fragiles: incluir TODO (submodulos, datos y binarios).
#  - undetected_chromedriver / selenium: motor del navegador anti-bloqueo.
#  - curl_cffi: trae libcurl-impersonate (DLLs); lo usa Amazon/meli_fetch.
#  - uvicorn / fastapi / starlette: backend web.
for pkg in ("undetected_chromedriver", "selenium", "curl_cffi",
            "uvicorn", "fastapi", "starlette"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# uvicorn resuelve estos por nombre en runtime -> asegurarlos explicitos.
hiddenimports += [
    "uvicorn.loops.auto", "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on", "uvicorn.lifespan.off",
    "uvicorn.logging",
]

# Datos de la app: van a la raiz del bundle (= mc.BASE_DIR cuando frozen).
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
    # No se usan en el flujo del backend; excluirlos adelgaza mucho el .exe.
    excludes=["pandas", "openpyxl", "matplotlib", "tkinter", "PyQt5", "PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="NuevosNegociosAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,                                   # sin ventana de consola
    icon="nuevos_negocios_ai_icono_windows.ico",
)
