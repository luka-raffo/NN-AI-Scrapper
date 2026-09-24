# -*- coding: utf-8 -*-
"""
Motor de descarga de MercadoLibre con navegador anti-deteccion (rapido).
========================================================================
Desde 2026 MELI reemplazo el proof-of-work de DataDome (que resolvia
meli_fetch.py) por un muro "suspicious-traffic" / account-verification que ya
NO trae un desafio para computar: exige un navegador REAL que ejecute su JS y
que NO parezca automatizado.

Comprobado empiricamente:
  - curl_cffi              -> muro (no ejecuta el JS del handshake de dispositivo)
  - Selenium/Chrome comun  -> muro (lo detectan como automatizado)
  - Chrome incognito real  -> PASA (sin login ni cookies)
  - undetected-chromedriver headful -> PASA igual que incognito

Este motor usa undetected-chromedriver headful con la ventana FUERA DE PANTALLA.
NO requiere login ni cookies. Optimizaciones de velocidad SEGURAS (no afectan la
deteccion anti-bot):

  1. Imagenes desactivadas + pageLoadStrategy=eager: la navegacion no espera a
     descargar/renderizar todo, solo el DOM basico; igual pollamos page_source.
  2. Pre-calentar los 4 dominios al arrancar (precalentar_paises) para que la
     primera consulta de cada pais no llegue en frio y no gaste el reintento.

IMPORTANTE (aprendido a la mala): NO usar fetch() para pedir el listado (las
peticiones fetch no cargan la cookie de dispositivo que MELI da solo en una
navegacion real -> caen en el muro), y NO martillar el endpoint (rafagas de
navegaciones marcan la IP y disparan el muro "suspicious-traffic" un rato).

Mantiene UN driver persistente y serializa con lock (un navegador no navega en
paralelo): la serie de paises regionales se hace en secuencia, ~6-8s c/u.
"""

import os
import sys
import threading
import time
from urllib.parse import urlsplit

import undetected_chromedriver as uc

import meli_common as mc

PRODUCT_MARKERS = ("poly-card", "ui-search-layout__item")
# Desafio anti-bot "micro-landing" (sep 2026): NO es un muro. La pagina corre un
# proof-of-work en JS (verifyChallenge) y redirige SOLA al listado real, en ~2-3 s
# (o a los 10 s por timeout, igual continua). Tratarlo como muro y recargar
# reinicia el desafio y nunca lo deja terminar: hay que ESPERARLO.
CHALLENGE_MARKERS = ("verifyChallenge", "micro-landing-container")
# Muro de verdad (no se resuelve solo): lo que queda de mc.BLOCK_MARKERS.
HARD_BLOCK_MARKERS = tuple(m for m in mc.BLOCK_MARKERS if m not in CHALLENGE_MARKERS)
CHALLENGE_WAIT_S = 20  # techo de espera cuando aparece el desafio (su timeout es 10 s)
WAIT_S = 10        # techo de espera a que hidraten las publicaciones
POLL_S = 0.3
WARMUP_S = 2.5     # espera tras entrar a la home para asentar la sesion
MAX_INTENTOS = 3   # reintentos si el listado cae en el muro
# Backoff creciente entre reintentos. El 1ro corto (el muro ya se detecto, no
# hay que esperar de mas); los siguientes mas largos porque, si el muro insiste,
# es que la sesion quedo marcada y conviene despegarse de la rafaga.
BACKOFF_S = (1.5, 4.0, 8.0)

# Homes por prefijo, para pre-calentar sin depender de un cat_id concreto.
HOMES = {
    "MLA": "https://www.mercadolibre.com.ar/",
    "MLM": "https://www.mercadolibre.com.mx/",
    "MLU": "https://www.mercadolibre.com.uy/",
    "MLB": "https://www.mercadolivre.com.br/",
}

# Pool: un navegador y un lock POR DOMINIO (netloc). Distintos paises usan
# distintos drivers -> corren en paralelo; el mismo pais comparte lock -> nunca
# dos consultas simultaneas al mismo dominio (no sube la carga por dominio, que
# es lo que dispara el muro). Los drivers se crean por demanda.
_drivers = {}      # netloc -> driver uc
_dlocks = {}       # netloc -> Lock (serializa las consultas de ese dominio)
_warmed = set()    # homes (por netloc) ya "calentadas"
_pool_guard = threading.Lock()    # protege los dicts _drivers/_dlocks (rapido)
_create_guard = threading.Lock()  # serializa TODA creacion de driver (patch de uc)


def _chrome_major():
    """Version mayor de Chrome instalada, para castear el chromedriver de uc.

    uc por defecto baja el driver de la ultima version publicada y falla si el
    Chrome local es anterior; fijar la mayor correcta evita ese desajuste.
    Windows: registro (BLBeacon). macOS: Info.plist del .app de Chrome.
    """
    if sys.platform == "darwin":
        import plistlib
        for app in ("/Applications/Google Chrome.app",
                    os.path.expanduser("~/Applications/Google Chrome.app")):
            try:
                with open(os.path.join(app, "Contents", "Info.plist"), "rb") as f:
                    ver = plistlib.load(f)["CFBundleShortVersionString"]
                return int(ver.split(".")[0])
            except Exception:
                continue
        return None
    try:
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                k = winreg.OpenKey(hive, r"Software\Google\Chrome\BLBeacon")
                ver, _ = winreg.QueryValueEx(k, "version")
                winreg.CloseKey(k)
                return int(ver.split(".")[0])
            except OSError:
                continue
    except Exception:
        pass
    return None  # que uc intente adivinar


def _crear_driver():
    opts = uc.ChromeOptions()
    opts.add_argument("--window-size=1400,1000")
    if sys.platform == "darwin":
        # macOS no deja ventanas fuera de pantalla (las trae de vuelta a la
        # vista): se minimizan tras crearlas (_ocultar_en_mac). Minimizada,
        # Chrome la trata como en segundo plano y frenaria timers y renderer,
        # que el desafio anti-bot necesita: estos flags lo evitan.
        opts.add_argument("--disable-background-timer-throttling")
        opts.add_argument("--disable-renderer-backgrounding")
    else:
        opts.add_argument("--window-position=-32000,-32000")  # fuera de pantalla
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    # Sin imagenes: el listado no las necesita y ahorra mucho ancho de banda.
    # OJO: NO desactivar JavaScript (el anti-bot necesita ejecutar su JS).
    opts.add_argument("--blink-settings=imagesEnabled=false")
    # La ventana vive fuera de pantalla; sin estos flags Chrome la considera
    # "ocluida" y frena el JS en segundo plano (y volveriamos a caer en el muro).
    opts.add_argument("--disable-backgrounding-occluded-windows")
    opts.add_argument("--disable-features=CalculateNativeWinOcclusion")
    # No esperar al 'load' completo: apenas el DOM basico. Igual pollamos/fetch.
    opts.page_load_strategy = "eager"
    driver = uc.Chrome(options=opts, headless=False, use_subprocess=True,
                       version_main=_chrome_major())
    _ocultar_de_taskbar(driver)
    _ocultar_en_mac(driver)
    return driver


def _ocultar_en_mac(driver):
    """macOS: minimiza la ventana del Chrome del pool (queda en el Dock)."""
    if sys.platform != "darwin":
        return
    try:
        driver.minimize_window()
    except Exception:
        pass


def _ocultar_de_taskbar(driver):
    """Saca de la barra de tareas las ventanas del Chrome de este driver.

    La ventana ya esta fuera de pantalla (--window-position=-32000,...), pero
    Windows igual le pone un boton en la barra de tareas. Le marcamos el estilo
    extendido WS_EX_TOOLWINDOW (y le quitamos WS_EX_APPWINDOW): las tool windows
    NO aparecen en la barra. NO usamos SW_HIDE a proposito: una ventana oculta la
    trata Chrome como "en background" y throttlea el JS del anti-bot; con
    SW_SHOWNOACTIVATE sigue "visible" para Chrome (fuera de pantalla) pero sin
    boton en la barra. Solo Windows; en otros SO es no-op.
    """
    if os.name != "nt":
        return
    pid = getattr(driver, "browser_pid", None)
    if not pid:
        return
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return

    user32 = ctypes.windll.user32
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_APPWINDOW = 0x00040000
    SW_HIDE = 0
    SW_SHOWNOACTIVATE = 4

    # En 64-bit hay que usar las variantes *Ptr para no truncar el handle/estilo.
    get_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
    set_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)

    def _reestilar(hwnd):
        user32.ShowWindow(hwnd, SW_HIDE)
        ex = get_long(hwnd, GWL_EXSTYLE)
        ex = (ex & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW
        set_long(hwnd, GWL_EXSTYLE, ex)
        user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def _buscar_y_ocultar():
        encontrados = [0]

        def _cb(hwnd, _):
            wpid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
            if wpid.value == pid and user32.IsWindowVisible(hwnd):
                try:
                    _reestilar(hwnd)
                    encontrados[0] += 1
                except Exception:
                    pass
            return True

        user32.EnumWindows(WNDENUMPROC(_cb), 0)
        return encontrados[0]

    # La ventana puede tardar un instante en existir tras crear el driver.
    for _ in range(20):
        try:
            if _buscar_y_ocultar() > 0:
                return
        except Exception:
            return
        time.sleep(0.25)


def _netloc_de(url):
    return urlsplit(url).netloc


def _lock_de(netloc):
    with _pool_guard:
        if netloc not in _dlocks:
            _dlocks[netloc] = threading.Lock()
        return _dlocks[netloc]


def _get_driver(netloc):
    """Driver del dominio (lo crea si no existe).

    TODA creacion de driver se serializa con _create_guard: uc parchea/renombra
    un binario compartido (chromedriver.exe -> undetected_chromedriver.exe) y dos
    creaciones simultaneas chocan (WinError 183). Como cada dominio se crea UNA
    sola vez y despues se reutiliza, serializar la creacion NO afecta el
    paralelismo de las consultas (que es navegacion, no creacion).
    """
    # camino rapido: ya existe (sin tocar _create_guard)
    with _pool_guard:
        d = _drivers.get(netloc)
        if d is not None:
            return d

    with _create_guard:
        # revisar de nuevo por si otro hilo lo creo mientras esperabamos.
        with _pool_guard:
            d = _drivers.get(netloc)
            if d is not None:
                return d
        nuevo = _crear_driver()
        with _pool_guard:
            _drivers[netloc] = nuevo
        return nuevo


def _reset_driver(netloc):
    with _pool_guard:
        d = _drivers.pop(netloc, None)
    try:
        if d:
            d.quit()
    except Exception:
        pass
    _warmed.discard(f"https://{netloc}/")


def _home_de(url):
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}/"


def _warmup(driver, url):
    """Entra a la home del dominio antes del primer listado, para asentar la
    sesion (la 1a navegacion en frio suele caer en el muro)."""
    home = _home_de(url)
    if home in _warmed:
        return
    try:
        driver.get(home)
        time.sleep(WARMUP_S)
        _esperar_desafio(driver)  # la home tambien puede traer el desafio
        _warmed.add(home)
    except Exception:
        pass


def _es_desafio(html):
    return (any(m in html for m in CHALLENGE_MARKERS)
            and not any(m in html for m in PRODUCT_MARKERS))


def _page_source(driver):
    # Mientras el desafio redirige, leer el DOM puede fallar un instante.
    try:
        return driver.page_source
    except Exception:
        return ""


def _esperar_desafio(driver):
    """Si la pagina actual es el desafio, espera a que redirija sola."""
    t0 = time.time()
    html = _page_source(driver)
    while _es_desafio(html) and time.time() - t0 < CHALLENGE_WAIT_S:
        time.sleep(POLL_S)
        html = _page_source(driver)
    return html


def _esperar_carga(driver):
    """Lee page_source cuando aparecen publicaciones o un muro de verdad.

    El desafio no corta la espera: extiende el techo a CHALLENGE_WAIT_S para
    darle tiempo a resolverse y redirigir al listado.
    """
    t0 = time.time()
    techo = WAIT_S
    html = _page_source(driver)
    while time.time() - t0 < techo:
        if any(m in html for m in PRODUCT_MARKERS):
            break
        if any(m in html for m in HARD_BLOCK_MARKERS):
            break
        if _es_desafio(html):
            techo = CHALLENGE_WAIT_S
        time.sleep(POLL_S)
        html = _page_source(driver)
    return html


def obtener_html(url, log=print):
    """Devuelve (status, html) del listado usando el navegador.

    Calienta el dominio, navega al listado, espera a que hidraten las
    publicaciones y, si cae en el muro, reintenta. Si el navegador murio, lo
    reinicia.
    """
    netloc = _netloc_de(url)
    # Lock POR DOMINIO: dos dominios distintos no se bloquean entre si (corren en
    # paralelo); dos consultas al mismo dominio se serializan.
    with _lock_de(netloc):
        for intento in range(1, MAX_INTENTOS + 1):
            try:
                driver = _get_driver(netloc)
                _warmup(driver, url)
                driver.get(url)
                html = _esperar_carga(driver)
                if not mc.esta_bloqueado(html):
                    return 200, html
                if intento == MAX_INTENTOS:
                    # Ultimo intento: dormir aca solo demora el 503. Si se tira el
                    # driver, para que la PROXIMA consulta arranque con sesion limpia.
                    log(f"      [{netloc}][{intento}/{MAX_INTENTOS}] muro; me rindo.")
                    _reset_driver(netloc)
                    break
                log(f"      [{netloc}][{intento}/{MAX_INTENTOS}] muro; reintento...")
                _warmed.discard(_home_de(url))  # recalentar por las dudas
                # Desde el 2do fallo el problema ya no es una sesion "fria":
                # MELI marco ESTA sesion, y recalentar el mismo Chrome no la
                # limpia (se veia un pais agotando los 3 intentos mientras los
                # otros pasaban al 1er reintento). Se tira el driver y se
                # levanta uno nuevo: sesion y cookies limpias, que es lo que
                # documentadamente pasa el muro.
                if intento >= 2:
                    log(f"      [{netloc}] sesion marcada; Chrome nuevo...")
                    _reset_driver(netloc)
                time.sleep(BACKOFF_S[min(intento - 1, len(BACKOFF_S) - 1)])
            except Exception as e:
                log(f"      [{netloc}] navegador cayo ({e}); reinicio y reintento...")
                _reset_driver(netloc)
                time.sleep(2)
        return 0, ""


def scrapear_categoria(cat_id, log=print, **kw):
    """Descarga y parsea una categoria. (estado, productos).

    estado = "ok" | "bloqueado" | "vacio". Misma firma que
    meli_fetch.scrapear_categoria (kw extra se ignoran) para ser intercambiable.
    """
    url = mc.url_mas_vendidos(cat_id)
    status, html = obtener_html(url, log=log)
    if not html or mc.esta_bloqueado(html):
        return "bloqueado", []
    productos = mc.parsear_productos(html)
    if not productos:
        return "vacio", []
    return "ok", productos


def _precalentar_uno(home, pref, log):
    """Crea el driver de un dominio y le calienta la home (para un hilo)."""
    netloc = _netloc_de(home)
    with _lock_de(netloc):
        try:
            driver = _get_driver(netloc)
            _warmup(driver, home)
            log(f"      precalentado {pref}")
        except Exception as e:
            log(f"      no se pudo precalentar {pref} ({e})")


def precalentar_paises(prefijos=("MLA", "MLM", "MLU", "MLB"), log=print):
    """Pre-visita las homes para asentar la sesion de cada pais de antemano.

    Pensado para llamarse en un hilo al arrancar el backend: cuando llegue la
    primera consulta, el dominio ya esta caliente y no cae en el muro en frio.
    Calienta cada pais en su propio driver y en paralelo (un hilo c/u), asi el
    boot no tarda 4x el arranque de un Chrome.
    """
    hilos = []
    for pref in prefijos:
        home = HOMES.get(pref)
        if not home:
            continue
        t = threading.Thread(target=_precalentar_uno, args=(home, pref, log),
                             daemon=True)
        t.start()
        hilos.append(t)
    for t in hilos:
        t.join()


def cerrar():
    """Cierra todos los navegadores del pool (llamar al apagar el backend)."""
    with _pool_guard:
        netlocs = list(_drivers.keys())
    for netloc in netlocs:
        _reset_driver(netloc)
