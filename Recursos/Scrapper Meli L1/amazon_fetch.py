# -*- coding: utf-8 -*-
"""
Motor de scraping de Amazon (amazon.com, amazon.com.mx y amazon.in).

Misma técnica que el scraper de MercadoLibre: curl_cffi con impersonate="chrome"
(fingerprint TLS de un Chrome real) para saltar las restricciones anti-bot.

Modelo: por cada CATEGORÍA se busca su NOMBRE en el buscador de Amazon usando el
filtro nativo de Amazon "Ordenar por: Los más vendidos" (Best Sellers). Es decir,
trae exactamente los productos —y en el mismo orden— que aparecen al buscar el
nombre de la categoría y cambiar el dropdown de "Destacados" a "Los más vendidos".

    estado, productos = buscar("auriculares inalambricos", "MX")
"""

import random
import re
import time
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from curl_cffi import requests

# Parámetro de orden de Amazon. "exact-aware-popularity-rank" == el dropdown
# "Los más vendidos" (MX) / "Best Sellers" (US). El default de Amazon sin este
# parámetro es "relevanceblender" == "Destacados" / "Featured".
SORT_MAS_VENDIDOS = "exact-aware-popularity-rank"

# site -> (host, Accept-Language, moneda i18n, lc-main, símbolo, nombre país)
SITES = {
    "US": ("www.amazon.com",    "en-US,en;q=0.9", "USD", "en_US", "US$", "Estados Unidos"),
    "MX": ("www.amazon.com.mx", "es-MX,es;q=0.9,en;q=0.8", "MXN", "es_MX", "$", "México"),
    "IN": ("www.amazon.in",     "en-IN,en;q=0.9,hi;q=0.8", "INR", "en_IN", "₹", "India"),
}
PAIS_NOMBRE = {k: v[5] for k, v in SITES.items()}

BLOCK_MARKERS = (
    "enter the characters you see below", "type the characters you see in this image",
    "robot check", "api-services-support@amazon.com", "to discuss automated access",
    "lo sentimos, algo salió mal", "caracteres que ves", "no somos robots",
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def _root(host):
    # www.amazon.com.mx -> amazon.com.mx ; www.amazon.com -> amazon.com
    return host[4:] if host.startswith("www.") else host


def _session(site):
    host, lang, cur, lc, _, _ = SITES[site]
    s = requests.Session(impersonate="chrome")
    s.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": lang,
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    })
    dom = "." + _root(host)
    s.cookies.set("i18n-prefs", cur, domain=dom)
    s.cookies.set("lc-main", lc, domain=dom)
    return s, host


def esta_bloqueado(html):
    h = html.lower()
    return any(m in h for m in BLOCK_MARKERS)


def _split_precio(txt, simbolo_site):
    """'$27.95' / 'US$ 1,299.00' -> (simbolo, '27.95')."""
    if not txt:
        return "", ""
    m = re.search(r"[\d][\d.,]*", txt)
    if not m:
        return "", ""
    return simbolo_site, m.group(0)


def _comprados(texto):
    """Extrae cantidad comprada el mes pasado (señal de más vendido).
    'Más de 1000 comprados el mes pasado' / '50+ bought in past month' -> (texto, valor_int)."""
    m = re.search(r"(?:m[áa]s de\s*)?\+?\s*([\d.,]+)\s*(mil|k)?\s*\+?\s*comprad\w*(?:\s+el mes pasado)?",
                  texto, re.I)
    if not m:
        m = re.search(r"([\d.,]+)\s*(k|mil)?\s*\+?\s*bought in past month", texto, re.I)
    if not m:
        return "", 0
    raw = re.sub(r"\s+", " ", m.group(0).strip())
    num = float(re.sub(r"[^\d.]", "", m.group(1).replace(",", "")) or 0)
    if (m.group(2) or "").lower() in ("mil", "k"):
        num *= 1000
    return raw, int(num)


def parsear_resultados(html, host, simbolo):
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select('div[data-component-type="s-search-result"]')
    productos = []
    for c in cards:
        asin = c.get("data-asin", "").strip()
        if not asin:
            continue
        h2 = c.select_one("h2 span") or c.select_one("h2 a span")
        titulo = h2.get_text(strip=True) if h2 else ""
        if not titulo:
            continue

        a = c.select_one("h2 a") or c.select_one("a.a-link-normal.s-no-outline") or c.select_one("a.a-link-normal")
        href = a.get("href", "") if a else ""
        link = ("https://" + host + href) if href.startswith("/") else href
        link = link.split("?")[0]

        pe = c.select_one(".a-price .a-offscreen")
        moneda, precio = _split_precio(pe.get_text(strip=True) if pe else "", simbolo)
        oe = c.select_one("span.a-price.a-text-price .a-offscreen")
        _, precio_orig = _split_precio(oe.get_text(strip=True) if oe else "", simbolo)

        re_el = c.select_one("i.a-icon-star-small span.a-icon-alt, i.a-icon-star span.a-icon-alt, .a-icon-alt")
        rating = ""
        if re_el:
            mr = re.search(r"[\d][.,]?\d?", re_el.get_text())
            rating = mr.group(0).replace(",", ".") if mr else ""
        rv = c.select_one("span.a-size-base.s-underline-text")
        reviews = rv.get_text(strip=True) if rv else ""

        img = c.select_one("img.s-image")
        imagen = (img.get("src") or "") if img else ""

        texto = c.get_text(" ", strip=True)
        vendidos, comprados_n = _comprados(texto)

        badge = c.select_one("span.a-badge-text")
        highlight = badge.get_text(strip=True) if badge else ""

        productos.append({
            "ranking": 0,
            "highlight": highlight,
            "titulo": titulo,
            "moneda": moneda or simbolo,
            "precio": precio,
            "precio_original": precio_orig,
            "descuento": "",
            "cuotas": "",
            "vendidos": vendidos,
            "_comprados": comprados_n,
            "rating": rating,
            "reviews": reviews,
            "envio": "",
            "vendedor": "",
            "mla_id": asin,
            "catalogo_id": "",
            "link": link,
            "imagen": imagen,
        })

    # El orden ya viene dado por Amazon (filtro "Los más vendidos"): respetamos ese
    # ranking tal cual aparece en la página. La señal "comprados el mes pasado" se
    # conserva sólo como dato informativo en cada producto, no para reordenar.
    for i, p in enumerate(productos, 1):
        p["ranking"] = i
        p.pop("_comprados", None)
    return productos


def buscar(query, site, log=print, max_retries=2, backoff_base=4, backoff_max=8):
    """Busca `query` en Amazon `site` (US|MX) y devuelve (estado, productos).
    estado = 'ok' | 'vacio' | 'bloqueado'."""
    site = (site or "US").upper()
    if site not in SITES:
        return "bloqueado", []
    host, _, _, _, simbolo, _ = SITES[site]
    # &s=... aplica el filtro "Ordenar por: Los más vendidos" directamente en Amazon.
    url = f"https://{host}/s?k={quote_plus(query)}&s={SORT_MAS_VENDIDOS}"

    for intento in range(1, max_retries + 1):
        s, _ = _session(site)
        try:
            s.get(f"https://{host}/", timeout=30)  # warm-up: cookies de sesión/locale
            res = s.get(url, timeout=30, allow_redirects=True)
            html = res.text
            if esta_bloqueado(html) or len(html) < 50000:
                espera = min(backoff_base * intento, backoff_max)
                log(f"      [amazon {site}] bloqueado/parcial; espero {espera}s y reintento...")
                time.sleep(espera)
                continue
            productos = parsear_resultados(html, host, simbolo)
            return ("ok" if productos else "vacio"), productos
        except Exception as e:
            log(f"      [amazon {site}] error de red ({e}); reintento...")
            time.sleep(4)

    return "bloqueado", []
