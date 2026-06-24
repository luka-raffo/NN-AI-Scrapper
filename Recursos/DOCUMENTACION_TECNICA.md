# Documentación Técnica — App "Más Vendidos MELI"

> Herramienta interna de Nuevos Negocios para explorar las categorías de
> MercadoLibre y traer, a demanda, el ranking de **productos más vendidos** de
> una categoría en **Argentina, México, Uruguay y Brasil**, comparándolos lado a lado.

---

## 1. Resumen en una línea

Una web (HTML+JS) muestra el árbol de categorías de MercadoLibre Argentina; al
elegir una categoría y uno o más países, un backend en Python **scrapea en vivo**
la página pública de "más vendidos" de cada país y devuelve los productos, que la
web pinta en columnas comparativas.

---

## 2. Arquitectura general

```
   ┌──────────────────────────────────────────────────────────────┐
   │                      NAVEGADOR (cualquiera)                    │
   │   htmlMvpNuevosNegociosAI.html  (UI + JS, sin frameworks)      │
   └───────────────┬──────────────────────────────────────────────┘
                   │  HTTPS (una sola URL)
                   ▼
   ┌──────────────────────────────────────────────────────────────┐
   │           TÚNEL CLOUDFLARE  (cloudflared.exe)                  │
   │   Expone a internet el backend que corre en la PC local       │
   └───────────────┬──────────────────────────────────────────────┘
                   │  http://localhost:8000
                   ▼
   ┌──────────────────────────────────────────────────────────────┐
   │            BACKEND  FastAPI  (api.py)  — en TU PC              │
   │   • Sirve el HTML en  /                                        │
   │   • /arbol, /mas-vendidos-pais, /categorias, ...              │
   │   • Resolver cross-país  +  caché en memoria (10 min)         │
   └───────────────┬──────────────────────────────────────────────┘
                   │  reutiliza el motor del scraper
                   ▼
   ┌──────────────────────────────────────────────────────────────┐
   │     MOTOR DE SCRAPING  (meli_fetch.py + meli_common.py)        │
   │   curl_cffi (fingerprint de Chrome) + resuelve el             │
   │   proof-of-work de DataDome → baja el HTML → parsea productos  │
   └───────────────┬──────────────────────────────────────────────┘
                   │  HTTPS
                   ▼
        www.mercadolibre.com.ar / .com.mx / .com.uy / mercadolivre.com.br
                  página pública  /mas-vendidos/<CAT_ID>
```

**Punto clave de diseño:** el backend corre en una **PC con IP residencial**.
MercadoLibre (vía DataDome) bloquea las IPs de datacenter (Render, Railway, VPS,
etc.), así que NO se puede mover a un hosting cloud común. Por eso el backend vive
en la PC y solo se **expone** con un túnel.

---

## 3. Componentes en detalle

### 3.1 Frontend — `htmlMvpNuevosNegociosAI.html`
Un solo archivo HTML con CSS y JavaScript vanilla (sin React/librerías). Partes:

- **Explorador de categorías (árbol):** al cargar pide `GET /arbol?pais=AR` y
  construye el árbol (Vertical → L1 → L2 → … hasta L7) con los **IDs reales** de
  ML (`MLA…`). Si el backend no responde, usa un árbol local de respaldo.
- **Selección:** el usuario elige una categoría (hoja) + "tipo de búsqueda" +
  una o más **fuentes** (ML Argentina / México / Uruguay / Brasil).
- **Búsqueda:** al tocar "Iniciar búsqueda", por **cada fuente en paralelo**
  llama a `GET /mas-vendidos-pais?ref=<ID_AR>&pais=<AR|MX|UY|BR>` y pinta una
  columna por país con sus productos (o un aviso "sin equivalente" / error).
- **Detección automática del backend (`API_BASE`):**
  - Si la página se sirve por http(s) (desde el túnel) → usa el **mismo origen**.
  - Si se abre como archivo local → `http://127.0.0.1:8000`.
  - Se puede forzar con `?api=https://...` o `localStorage.apiBase`.
- **Scroll:** la barra de categorías es *sticky* con scroll propio; el resto de
  la página scrollea normal (importante porque el árbol AR tiene ~12.000 nodos).

### 3.2 Backend — `api.py` (FastAPI + Uvicorn)
Expone la API y **sirve el propio HTML**. Responsabilidades:
- Cargar los catálogos de los 4 países y construir índices de búsqueda.
- **Resolver** la categoría equivalente entre países (ver §5).
- Llamar al motor de scraping y **cachear** las respuestas 10 minutos.
- CORS abierto (cualquier origen puede consumirlo).

Caché: diccionario en memoria `cat_id → (timestamp, respuesta)`, TTL 600 s. Con
un *lock* por categoría para no scrapear la misma cosa dos veces en paralelo.

### 3.3 Motor de scraping — `meli_fetch.py` + `meli_common.py`
- **`meli_fetch.obtener_html(url)`**: usa `curl_cffi` con `impersonate="chrome"`
  (replica el *fingerprint* TLS de un Chrome real). Si ML responde con la pantalla
  de bloqueo de DataDome/BotManager, lee la cookie `_bmstate`, **resuelve el
  proof-of-work** (busca por fuerza bruta un número cuyo `SHA256` empiece con N
  ceros), setea las cookies `_bmc`/`_bm_skipml` y reintenta. Con *backoff* y
  reintentos cortos para la API (falla rápido, ~10 s máx).
- **`meli_common.parsear_productos(html)`**: con BeautifulSoup extrae de cada
  tarjeta: ranking, título, precio, precio original, descuento, cuotas, vendidos,
  rating, reviews, envío, vendedor, `mla_id`, link e imagen.
- **`scraper_browser.py`** (fallback, opcional, NO lo usa la API): Chrome real vía
  Selenium para casos que `curl_cffi` deja truncados o con captcha.

### 3.4 Catálogos de categorías
- `categorias_ar.json`, `categorias_mx.json`, `categorias_uy.json`,
  `categorias_br.json`: lista plana de `{id, nombre, nivel, ruta}` por país
  (~12.000 categorías cada uno, hasta nivel L7).
- Se generan a partir de los dumps `HTTP_Request *.json` (respuestas crudas de la
  API oficial de categorías de ML: cada nodo con su `path_from_root` y sus hijos).
- `NN AI - Verticales MELI.csv`: catálogo curado anterior (verticales Bidcom),
  usado solo como respaldo si no existe `categorias_ar.json`.

---

## 4. Flujo de una búsqueda (ciclo de vida de un request)

```
1. Navegador abre la URL pública            → backend devuelve el HTML
2. JS pide  GET /arbol?pais=AR              → árbol de categorías (IDs MLA reales)
3. Usuario elige categoría (ej. MLA1000) + fuentes [AR, MX, UY, BR] + "Iniciar"
4. Por cada país, en paralelo:
     GET /mas-vendidos-pais?ref=MLA1000&pais=BR
        ├─ resolver_equivalente(MLA1000, BR) → MLB1000   (ver §5)
        ├─ ¿está en caché y fresco? → sí: devuelve cacheado
        └─ no: scrapear_categoria(MLB1000)
                 ├─ baja https://mercadolivre.com.br/mais-vendidos/MLB1000
                 ├─ si DataDome bloquea → resuelve proof-of-work y reintenta
                 └─ parsea productos → guarda en caché → responde JSON
5. JS pinta una columna por país con las tarjetas de producto
```

---

## 5. Resolver cross-país (cómo se "traducen" las categorías)

El árbol que ve el usuario es el de **Argentina**. Para traer los mismos productos
en otro país hay que encontrar el ID equivalente (los IDs cambian de prefijo y, a
veces, de número entre países). `resolver_equivalente(ref_id, pais)` prueba, en
orden:

1. **Mismo país:** si el ID ya es de ese país, se usa tal cual.
2. **Swap de prefijo:** `MLA1000 → MLB1000`, verificando que exista en el catálogo
   destino. (La taxonomía de ML comparte el número en la mayoría de los casos.)
3. **Ruta exacta:** match por la ruta completa normalizada (sin acentos), para
   respetar la rama correcta cuando el número difiere.
4. **Traducción aprendida ES→idioma destino:** clave para **Brasil (portugués)**.
   Se aprende de los propios datos: las categorías que SÍ comparten número entre
   AR y BR funcionan como "diccionario Rosetta" (nombre_AR ↔ nombre_BR). Con eso
   se arma un diccionario **por segmento** y **por palabra**
   (ej. *Parlantes→Alto-falantes*, *Repuestos→Peças*, *Auto y Camioneta→Carros e
   Caminhonetes*). Luego se traduce la ruta de la categoría AR y se busca su
   equivalente real en el destino.
5. **Nombre + nivel** como último recurso.

Si nada matchea → la columna de ese país muestra "sin categoría equivalente"
(no se inventa un match incorrecto).

**Cobertura de matcheo AR → otros países:**

| País    | Cobertura |
|---------|-----------|
| Uruguay | ~93%      |
| México  | ~87%      |
| Brasil  | ~76%      |

(El resto son categorías que directamente no existen en ese país.)

---

## 6. Endpoints del backend

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/` | Sirve la web (el HTML). |
| `GET` | `/health` | Chequeo de estado `{"status":"ok"}`. |
| `GET` | `/arbol?pais=AR` | Árbol anidado de categorías con IDs reales (para el explorador). |
| `GET` | `/categorias?pais=&nivel=` | Catálogo plano (lista) por país/nivel. |
| `GET` | `/mas-vendidos/{cat_id}` | Más vendidos de un ID exacto. `?nocache=1` ignora caché. |
| `GET` | `/mas-vendidos-pais?ref=&pais=` | Resuelve el equivalente de `ref` en `pais` y scrapea. |
| `POST`| `/mas-vendidos` | Igual que el GET por ID, con body `{"categoria":"MLA1000"}`. |
| `GET` | `/paises` | Lista de países soportados. |
| `GET` | `/api` | Info del servicio. |

**Ejemplo de respuesta de `/mas-vendidos-pais`:**
```json
{
  "encontrado": true,
  "ref": "MLA1000",
  "equivalente_id": "MLB1000",
  "categoria": "Eletrônicos, Áudio e Vídeo",
  "pais": "BR",
  "cantidad": 20,
  "cacheado": false,
  "productos": [
    { "ranking": 1, "titulo": "...", "precio": "1.066", "moneda": "R$",
      "descuento": "", "cuotas": "...", "vendidos": "...", "rating": "...",
      "vendedor": "...", "link": "https://...", "imagen": "https://..." }
  ]
}
```

---

## 7. Despliegue y operación

- **Backend:** corre en la PC con `uvicorn api:app --host 0.0.0.0 --port 8000`.
  Como sirve también el HTML, hay **una sola URL** para todo.
- **Túnel:** `cloudflared.exe tunnel --url http://localhost:8000` da una URL
  pública `https://XXXX.trycloudflare.com`.
  > La versión gratis es **efímera**: la URL cambia y el túnel puede cortarse.
  > Para una URL **fija** se necesita un *named tunnel* (cuenta Cloudflare +
  > dominio) o **Tailscale Funnel** (gratis, sin dominio, requiere instalar
  > Tailscale con permisos de admin).
- **Scripts:**
  - `start.bat` → solo el backend (uso local).
  - `tunnel.bat` → solo el túnel.
  - `PUBLICO.bat` → backend + túnel juntos.
  - `MANTENER ONLINE.bat` → "guardián": mantiene backend + túnel, los reinicia
    si se caen y escribe el link actual en `Escritorio\LINK DE LA APP.txt`.

**Por qué no está en un hosting cloud:** DataDome bloquea IPs de datacenter; el
scraper solo funciona confiable desde una IP residencial (tu PC). Alternativa
24/7 sin la PC: hosting + proxies residenciales (ScraperAPI/ZenRows/BrightData),
que es pago.

---

## 8. Mapa de archivos

```
Recursos/
├─ htmlMvpNuevosNegociosAI.html     ← la web (UI + JS)
├─ DOCUMENTACION_TECNICA.md         ← este documento
├─ INTEGRACION.md                   ← cómo levantarla / publicarla
└─ Scrapper Meli L1/
   ├─ api.py                        ← backend FastAPI (endpoints + resolver + caché)
   ├─ meli_fetch.py                 ← motor de descarga (curl_cffi + proof-of-work)
   ├─ meli_common.py                ← carga de catálogos + parseo de productos
   ├─ scraper_l1.py                 ← scraper por lote (CLI, opcional)
   ├─ scraper_browser.py            ← fallback con Selenium (opcional)
   ├─ fetch_categorias.py           ← genera categorias_*.json desde la API oficial
   ├─ categorias_ar/mx/uy/br.json   ← catálogos por país (~12k c/u)
   ├─ HTTP_Request *.json           ← dumps crudos de categorías (fuente de los .json)
   ├─ NN AI - Verticales MELI.csv   ← catálogo curado (respaldo AR)
   ├─ cloudflared.exe               ← binario del túnel
   ├─ mantener_online.ps1           ← guardián (auto-restart + link)
   └─ *.bat                         ← scripts de arranque
```

---

## 9. Stack técnico

- **Frontend:** HTML5, CSS3, JavaScript vanilla (sin build, sin dependencias).
- **Backend:** Python 3 · FastAPI · Uvicorn · Pydantic.
- **Scraping:** curl_cffi (TLS impersonation) · BeautifulSoup4 · lxml · pandas/openpyxl.
- **Exposición:** Cloudflare Tunnel (cloudflared).
- **Sin base de datos:** los catálogos son archivos JSON y la caché es en memoria.

---

## 10. Limitaciones conocidas

1. **Depende de la PC encendida** con el backend + túnel corriendo.
2. **URL del túnel gratis cambia** al reiniciarse (solucionable con URL fija).
3. **Brasil ~76%** de matcheo (portugués); el resto no tiene equivalente o tiene
   estructura distinta.
4. **DataDome:** si ML endurece la protección, puede haber bloqueos puntuales
   (la API responde HTTP 503 y la columna avisa "reintentá en unos segundos").
5. **Uso intensivo / niveles muy profundos** pueden requerir proxies residenciales.
6. El árbol AR completo (~12k nodos) se renderiza entero en el DOM; funciona, pero
   en equipos lentos puede notarse al abrir/buscar (mejorable con render diferido).
```
