# -*- coding: utf-8 -*-
"""
Backend a demanda - Scrapper Meli
=================================
API HTTP que recibe UNA categoria y devuelve sus productos mas vendidos.

Reutiliza el mismo motor que el scraper CLI (curl_cffi + proof-of-work DataDome).

Levantar el servidor:
    py -m uvicorn api:app --host 0.0.0.0 --port 8000

Endpoints:
    GET  /                         -> info
    GET  /health                   -> {"status":"ok"}
    GET  /categorias               -> lista de categorias conocidas del CSV
    GET  /mas-vendidos/{cat_id}    -> productos mas vendidos de esa categoria
         ?nocache=1                -> ignora cache y vuelve a scrapear
    POST /mas-vendidos             -> body {"categoria": "MLA1000"}

Ejemplo:
    GET http://localhost:8000/mas-vendidos/MLA1000

Respuesta:
    {
      "categoria_id": "MLA1000",
      "categoria": "Electrónica, Audio y Video",
      "url": "https://www.mercadolibre.com.ar/mas-vendidos/MLA1000",
      "cantidad": 20,
      "cacheado": false,
      "productos": [ {ranking, titulo, precio, ...}, ... ]
    }
"""

import csv
import json
import os
import re
import threading
import time
import unicodedata

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import meli_common as mc
import meli_fetch as mf

CACHE_TTL_S = 600          # 10 min: respuestas cacheadas para no re-scrapear de mas
CAT_ID_RE = re.compile(r"^ML[ABMU]\d+$")  # A=Argentina B=Brasil M=Mexico U=Uruguay

# HTML de la web (esta una carpeta arriba, en Recursos/).
HTML_FILE = os.path.normpath(os.path.join(mc.BASE_DIR, "..", "htmlMvpNuevosNegociosAI.html"))

# Prefijo de ID por pais (inverso de mc.PAIS_DE_PREFIJO).
PREFIJO_DE_PAIS = {v: k for k, v in mc.PAIS_DE_PREFIJO.items()}  # AR->MLA, MX->MLM, ...

app = FastAPI(title="Scrapper Meli - Más vendidos a demanda", version="1.0")

# CORS abierto para que la web pueda consumirlo desde el navegador.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ----------------------- Catalogo de nombres (AR + MX) -----------------------
def _cargar_nombres():
    nombres = {}
    for p in ("AR", "MX", "UY", "BR"):
        for c in mc.cargar_catalogo(p):
            nombres.setdefault(c["id"], c.get("nombre", ""))
    return nombres

NOMBRES = _cargar_nombres()


# ----------------------- Indices de catalogo y resolver cross-pais -----------------------
def _norm(s):
    """minusculas + sin acentos, para matchear nombres entre paises."""
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _segs(ruta):
    return [s for s in (ruta or "").split(" > ") if s.strip()]


def _norm_ruta_segs(segs):
    return " > ".join(_norm(s) for s in segs)


def _construir_indices():
    """Por pais: set de IDs, indice por (nivel,nombre), por ruta normalizada y
    meta global id->(nivel,nombre,ruta)."""
    indices = {}
    meta_global = {}
    for pais in ("AR", "MX", "UY", "BR"):
        cats = mc.cargar_catalogo(pais)
        ids = set()
        por_nombre = {}
        por_ruta = {}
        for c in cats:
            cid = c["id"]
            nivel = c.get("nivel", "")
            nombre = c.get("nombre", "")
            ruta = c.get("ruta", "") or nombre
            ids.add(cid)
            por_nombre.setdefault((nivel, _norm(nombre)), cid)
            por_ruta.setdefault(_norm_ruta_segs(_segs(ruta)), cid)
            meta_global.setdefault(cid, (nivel, nombre, ruta))
        indices[pais] = {"ids": ids, "por_nombre": por_nombre, "por_ruta": por_ruta}
    return indices, meta_global


_INDICES, _META = _construir_indices()


def _construir_traduccion():
    """Aprende traduccion de nombres AR->pais desde las categorias que comparten
    numero de ID (mismo nodo en ambos paises). Esas parejas (nombre_AR, nombre_dest)
    -> diccionario por-segmento. Clave para Brasil (portugues).

    Devuelve {pais: {norm(seg_es): norm(seg_dest)}} eligiendo la traduccion mas
    frecuente para cada segmento.
    """
    trad = {}
    ar_ids = _INDICES["AR"]["ids"]
    for pais in ("MX", "UY", "BR"):
        prefijo = PREFIJO_DE_PAIS[pais]
        ids_dest = _INDICES[pais]["ids"]
        seg_cnt = {}    # norm(seg_es) -> {norm(seg_dest): veces}
        word_cnt = {}   # norm(palabra_es) -> {norm(palabra_dest): veces}
        for ar_id in ar_ids:
            tgt = prefijo + ar_id[3:]
            if tgt not in ids_dest:
                continue
            a = _segs(_META[ar_id][2])
            b = _segs(_META[tgt][2])
            if len(a) != len(b):
                continue
            for x, y in zip(a, b):
                nx, ny = _norm(x), _norm(y)
                seg_cnt.setdefault(nx, {})
                seg_cnt[nx][ny] = seg_cnt[nx].get(ny, 0) + 1
                wx, wy = nx.split(), ny.split()
                if len(wx) == len(wy):  # mismo largo -> alineo palabra a palabra
                    for px, py in zip(wx, wy):
                        word_cnt.setdefault(px, {})
                        word_cnt[px][py] = word_cnt[px].get(py, 0) + 1
        trad[pais] = {
            "seg": {k: max(v, key=v.get) for k, v in seg_cnt.items()},
            "word": {k: max(v, key=v.get) for k, v in word_cnt.items()},
        }
    return trad


_TRADUCCION = _construir_traduccion()


def _traducir_seg(trad, norm_seg):
    """Traduce un segmento: primero entero; si no, palabra por palabra."""
    entero = trad["seg"].get(norm_seg)
    if entero:
        return entero
    palabras = trad["word"]
    return " ".join(palabras.get(p, p) for p in norm_seg.split())


def resolver_equivalente(ref_id, pais):
    """ID equivalente de ref_id en otro pais.

    1) Mismo pais.
    2) Swap de prefijo (MLA1000 -> MLB1000) si el ID existe en el destino.
    3) Match por RUTA completa normalizada (respeta la rama).
    4) Traduccion aprendida ES->idioma destino: traduce la ruta segmento a
       segmento y la busca en el destino (clave para Brasil/portugues).
    5) Traduccion del nombre de hoja + nivel.
    6) Ultimo recurso: match por (nivel, nombre) tal cual.
    Devuelve el ID equivalente o None.
    """
    ref_id = (ref_id or "").strip().upper()
    pais = (pais or "AR").upper()
    prefijo = PREFIJO_DE_PAIS.get(pais)
    idx = _INDICES.get(pais)
    if not prefijo or not idx:
        return None

    # 1) mismo pais
    if ref_id[:3] == prefijo:
        return ref_id if ref_id in idx["ids"] else (ref_id if CAT_ID_RE.match(ref_id) else None)

    # 2) swap de prefijo verificando que exista
    swapped = prefijo + ref_id[3:]
    if swapped in idx["ids"]:
        return swapped

    nivel, nombre, ruta = _META.get(ref_id, ("", "", ""))
    segs = _segs(ruta)

    # 3) ruta exacta normalizada
    if segs:
        hit = idx["por_ruta"].get(_norm_ruta_segs(segs))
        if hit:
            return hit

    # 4) y 5) traduccion aprendida (ES -> destino, ej. portugues)
    trad = _TRADUCCION.get(pais)
    if trad and segs:
        tsegs = [_traducir_seg(trad, _norm(s)) for s in segs]
        hit = idx["por_ruta"].get(" > ".join(tsegs))
        if hit:
            return hit
        hit = idx["por_nombre"].get((nivel, tsegs[-1]))
        if hit:
            return hit

    # 6) ultimo recurso: nombre tal cual
    if nombre:
        return idx["por_nombre"].get((nivel, _norm(nombre)))
    return None


# ----------------------- Arbol de categorias (anidado, con IDs reales) -----------------------
def _arbol_ar():
    """Arbol Vertical > L1 > L2 > L3 construido desde el CSV (IDs reales MLA)."""
    verticales = {}     # vertical -> nodo
    orden_v = []
    with open(mc.CSV_FILE, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            vert = (row.get("Vertical") or "Otras").strip() or "Otras"
            if vert not in verticales:
                verticales[vert] = {
                    "id": "vert-" + _norm(vert).replace(" ", "-").replace("&", "y"),
                    "name": vert, "level": "Vertical", "children": [], "_idx": {},
                }
                orden_v.append(vert)
            vnode = verticales[vert]

            niveles = (
                ("L1", (row.get("L1 ID") or "").strip(), (row.get("L1 Nombre") or "").strip()),
                ("L2", (row.get("L2 ID") or "").strip(), (row.get("L2 Nombre") or "").strip()),
                ("L3", (row.get("L3 ID") or "").strip(), (row.get("L3 Nombre") or "").strip()),
            )
            cursor = vnode
            for nivel, cid, nombre in niveles:
                if not cid:
                    break
                hijo = cursor["_idx"].get(cid)
                if hijo is None:
                    hijo = {"id": cid, "name": nombre, "level": nivel,
                            "children": [], "_idx": {}}
                    cursor["_idx"][cid] = hijo
                    cursor["children"].append(hijo)
                cursor = hijo

    def limpiar(nodo):
        nodo.pop("_idx", None)
        if nodo.get("children"):
            for h in nodo["children"]:
                limpiar(h)
        else:
            nodo.pop("children", None)
        return nodo

    return [limpiar(verticales[v]) for v in orden_v]


def _arbol_otro_pais(pais):
    """Arbol para MX/UY/BR reconstruido desde la 'ruta' (nombres) del catalogo JSON."""
    cats = mc.cargar_catalogo(pais)
    raiz = {"children": [], "_idx": {}}
    orden = {"L1": 0, "L2": 1, "L3": 2}
    for c in sorted(cats, key=lambda x: (orden.get(x.get("nivel"), 9), x.get("ruta", ""))):
        partes = [p.strip() for p in (c.get("ruta") or c.get("nombre", "")).split(" > ") if p.strip()]
        cursor = raiz
        for i, parte in enumerate(partes):
            key = _norm(parte)
            hijo = cursor["_idx"].get(key)
            if hijo is None:
                es_hoja = (i == len(partes) - 1)
                hijo = {"id": c["id"] if es_hoja else "grp-" + key,
                        "name": parte, "level": c.get("nivel") if es_hoja else "",
                        "children": [], "_idx": {}}
                cursor["_idx"][key] = hijo
                cursor["children"].append(hijo)
            cursor = hijo

    def limpiar(nodo):
        nodo.pop("_idx", None)
        if nodo.get("children"):
            for h in nodo["children"]:
                limpiar(h)
        else:
            nodo.pop("children", None)
        return nodo

    return [limpiar(h) for h in raiz["children"]]


# ----------------------- Cache simple en memoria con TTL -----------------------
_cache = {}            # cat_id -> (timestamp, payload)
_locks = {}            # cat_id -> Lock (evita scrapear la misma cat en paralelo)
_locks_guard = threading.Lock()


def _lock_de(cat_id):
    with _locks_guard:
        if cat_id not in _locks:
            _locks[cat_id] = threading.Lock()
        return _locks[cat_id]


class CategoriaIn(BaseModel):
    categoria: str


def _resolver(cat_id: str, nocache: bool):
    cat_id = cat_id.strip().upper()
    if not CAT_ID_RE.match(cat_id):
        raise HTTPException(status_code=400,
                            detail=f"ID de categoria invalido: '{cat_id}'. "
                                   "Debe tener formato MLA seguido de numeros, ej. MLA1000.")

    # cache hit
    if not nocache:
        hit = _cache.get(cat_id)
        if hit and (time.time() - hit[0]) < CACHE_TTL_S:
            payload = dict(hit[1])
            payload["cacheado"] = True
            return payload

    # Un solo scrape simultaneo por categoria
    with _lock_de(cat_id):
        # revisar de nuevo por si otro hilo ya lo trajo mientras esperabamos el lock
        if not nocache:
            hit = _cache.get(cat_id)
            if hit and (time.time() - hit[0]) < CACHE_TTL_S:
                payload = dict(hit[1])
                payload["cacheado"] = True
                return payload

        # Reintentos cortos: una API no debe colgar 80s. Si bloquea, 503 rapido.
        estado, productos = mf.scrapear_categoria(
            cat_id, max_retries=2, backoff_base=4, backoff_max=6)
        if estado == "bloqueado":
            raise HTTPException(status_code=503,
                                detail="MercadoLibre bloqueo la peticion (DataDome). "
                                       "Reintenta en unos segundos.")

        payload = {
            "categoria_id": cat_id,
            "categoria": NOMBRES.get(cat_id, ""),
            "pais": mc.PAIS_DE_PREFIJO.get(cat_id[:3], ""),
            "url": mc.url_mas_vendidos(cat_id),
            "cantidad": len(productos),
            "cacheado": False,
            "productos": productos,
        }
        _cache[cat_id] = (time.time(), payload)
        return payload


# ----------------------- Endpoints -----------------------
@app.get("/")
def root():
    # Sirve la web directamente desde el backend: una sola URL publica para todos.
    if os.path.exists(HTML_FILE):
        return FileResponse(HTML_FILE, media_type="text/html")
    return {
        "servicio": "Scrapper Meli - mas vendidos a demanda",
        "uso": "GET /mas-vendidos/MLA1000",
        "endpoints": ["/health", "/categorias", "/arbol", "/mas-vendidos/{cat_id}",
                      "/mas-vendidos-pais", "POST /mas-vendidos"],
    }


@app.get("/api")
def api_info():
    return {
        "servicio": "Scrapper Meli - mas vendidos a demanda",
        "uso": "GET /mas-vendidos/MLA1000",
        "endpoints": ["/health", "/categorias", "/arbol", "/mas-vendidos/{cat_id}",
                      "/mas-vendidos-pais", "POST /mas-vendidos"],
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/categorias")
def categorias(pais: str = Query("AR"), nivel: str = Query("todas")):
    """Categorias por pais y nivel.

    pais: AR (Argentina, del CSV) | MX (Mexico, del arbol API).
    nivel: todas (default) | l1 | l2 | l3.
    Devuelve {id, nombre, nivel, vertical, ruta, pais}.
    """
    nivel = (nivel or "todas").lower()
    todas = mc.cargar_catalogo(pais)
    if nivel in ("l1", "l2", "l3"):
        todas = [c for c in todas if c["nivel"].lower() == nivel]
    return todas


@app.get("/paises")
def paises():
    """Paises disponibles."""
    return [{"codigo": "AR", "nombre": "Argentina"},
            {"codigo": "MX", "nombre": "México"},
            {"codigo": "UY", "nombre": "Uruguay"},
            {"codigo": "BR", "nombre": "Brasil"}]


ARBOL_AR_FILE = os.path.join(mc.BASE_DIR, "arbol_ar.json")


@app.get("/arbol")
def arbol(pais: str = Query("AR")):
    """Arbol anidado de categorias con IDs reales, para el explorador del front.

    AR: usa arbol_ar.json (arbol real completo de ML) si existe; si no, el CSV de
    verticales. MX/UY/BR se reconstruyen desde la ruta del catalogo.
    """
    pais = (pais or "AR").upper()
    if pais == "AR":
        if os.path.exists(ARBOL_AR_FILE):
            with open(ARBOL_AR_FILE, encoding="utf-8") as f:
                return json.load(f)
        return _arbol_ar()
    return _arbol_otro_pais(pais)


@app.get("/mas-vendidos-pais")
def mas_vendidos_pais(ref: str = Query(...), pais: str = Query(...),
                      nocache: int = Query(0)):
    """Mas vendidos de la categoria equivalente a `ref` en `pais`.

    Resuelve el ID de referencia (de cualquier pais) a su equivalente en el
    pais pedido (swap de prefijo + fallback por nombre) y scrapea ese ID.
    Si no hay equivalente, devuelve {"encontrado": false} con HTTP 200.
    """
    pais = (pais or "AR").upper()
    if pais not in PREFIJO_DE_PAIS:
        raise HTTPException(status_code=400, detail=f"Pais invalido: '{pais}'.")

    equivalente = resolver_equivalente(ref, pais)
    if not equivalente:
        return {
            "encontrado": False,
            "pais": pais,
            "ref": ref,
            "mensaje": f"Sin categoria equivalente en {pais}.",
            "productos": [],
            "cantidad": 0,
        }

    payload = _resolver(equivalente, nocache=bool(nocache))
    payload["encontrado"] = True
    payload["ref"] = ref
    payload["equivalente_id"] = equivalente
    return payload


@app.get("/mas-vendidos/{cat_id}")
def mas_vendidos(cat_id: str, nocache: int = Query(0)):
    return _resolver(cat_id, nocache=bool(nocache))


@app.post("/mas-vendidos")
def mas_vendidos_post(body: CategoriaIn):
    return _resolver(body.categoria, nocache=False)
