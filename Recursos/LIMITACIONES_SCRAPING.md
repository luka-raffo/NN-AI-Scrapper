# Limitaciones de Scraping — de lo general a lo específico

> Guía en 3 niveles: **(1)** limitaciones de *cualquier* proyecto de scraping,
> **(2)** limitaciones propias de marketplaces tipo MercadoLibre/Amazon, y
> **(3)** los números y comportamientos exactos de *este* proyecto
> (`api.py`, `meli_fetch.py`, `meli_common.py`, `amazon_fetch.py`).
> Sirve como checklist para evaluar o replicar este enfoque en otro scraper.

---

## 1. Limitaciones generales (aplican a cualquier proyecto de scraping)

### 1.1 Legal / Términos de Servicio
- Casi todo sitio prohíbe el scraping en sus Términos de Servicio, aunque la
  página sea pública. Es un riesgo **contractual/civil**, no solo técnico.
- `robots.txt` no es ley, pero ignorarlo agrava el argumento en contra si hay
  un reclamo. Conviene revisarlo antes de scrapear un sitio nuevo.
- Regla general: usar los datos para **análisis interno**, no para
  redistribuirlos, revenderlos o reconstruir el catálogo del sitio de origen.

### 1.2 Reputación de IP (el límite más duro de todos)
- Los sistemas anti-bot (DataDome, Akamai, Cloudflare, PerimeterX, "Robot
  Check" de Amazon, etc.) clasifican la IP **antes** de mirar el resto de la
  request. Una IP de datacenter (AWS, GCP, Azure, Render, Railway, cualquier
  VPS) parte con desventaja o bloqueo directo, sin importar qué tan bien
  imitado esté el request.
- Una IP **residencial** (tu PC/oficina con ISP normal) tiene reputación alta
  desde el día 1. Es la variable que más pesa, más que cualquier header o
  fingerprint TLS.
- Corolario: si el proyecto *tiene* que correr 24/7 en la nube, la única forma
  confiable es pagar un servicio de **proxies residenciales/mobile**
  (Bright Data, Oxylabs, ScraperAPI, ZenRows, etc.). No hay atajo gratis.

### 1.3 Sistemas anti-bot: qué chequean
- **Fingerprint TLS/HTTP2** (ClientHello, orden de headers, cipher suites):
  un `requests`/`urllib` normal de Python se detecta al instante porque su
  fingerprint no es el de un browser real. Librerías como `curl_cffi` o
  `curl-impersonate` clonan el fingerprint de Chrome/Firefox para evadir esto.
- **Proof-of-Work / desafíos JS**: el servidor manda un cálculo (ej. buscar un
  hash con N ceros al inicio) que un browser real resuelve con JS; hay que
  resolverlo a mano en el scraper.
- **CAPTCHA visual**: la defensa más dura; no hay solución automática
  "gratis" y ética — normalmente implica resolución manual o servicios de
  terceros (con sus propios problemas legales/éticos).
- **Comportamiento**: demasiadas requests parecidas muy rápido, sin
  variación de headers/user-agent, sin delays "humanos", dispara bloqueos
  aunque el fingerprint sea perfecto.

### 1.4 No hay un "rate limit" documentado
- A diferencia de una API oficial (que publica límites, ej. "60 req/min"),
  scrapear una página pública no tiene contrato: el límite real es el que
  el sistema anti-bot decide, y puede cambiar sin aviso. Se descubre
  empíricamente con reintentos + backoff, nunca se puede asumir un número fijo.

### 1.5 Fragilidad estructural
- El scraper depende de clases CSS / estructura HTML específicas. Un
  rediseño del sitio (común, sin aviso) puede romper el parseo de un día
  para el otro. No hay versión "estable" garantizada como en una API.

### 1.6 Completitud de datos limitada
- Sin un browser real (headless), solo se ve el HTML que el servidor manda
  en la respuesta inicial. Contenido cargado por scroll infinito, tabs, o
  JS diferido puede no estar disponible sin Selenium/Playwright.
- Normalmente solo se accede a lo que la página **muestra** (ej. el top N de
  un listado), no a la base de datos completa del sitio.

### 1.7 Solo presente, no histórico
- Cada scrape es una foto del momento (precio, stock, ranking). Si se
  necesita histórico, hay que guardarlo vos mismo (no lo provee el sitio).

### 1.8 Escalar = más riesgo, no menos
- Subir el paralelismo (muchas categorías/queries a la vez) multiplica la
  chance de bloqueo total, incluso si cada request individual es "correcta".
  El anti-bot mira patrones agregados, no solo request-por-request.

### 1.9 Disponibilidad atada a un proceso que alguien tiene que mantener vivo
- Si no corre en un hosting administrado, alguien tiene que dejar la PC/proceso
  encendido. No hay auto-recuperación real salvo que se programe un guardián
  (ver `mantener_online.ps1` en este proyecto) — y aun así depende de la
  energía/red del lugar físico.

---

## 2. Limitaciones específicas de marketplaces tipo MercadoLibre / Amazon

### 2.1 No existe una API pública para "más vendidos por categoría"
- La API oficial de MercadoLibre **no** expone búsqueda por categoría ni
  highlights para apps de terceros (devuelve 403 con esta app) — no es que no
  se haya implementado, es que **no está disponible** ese endpoint.
- Amazon tampoco tiene un endpoint público de bestsellers filtrable a
  demanda para terceros.
- Por eso ambos motores scrapean **la página web pública**, no una API.

### 2.2 Qué requests se pueden hacer contra MercadoLibre (y qué no)
**Sí se puede:**
- `GET https://www.mercadolibre.com.<país>/mas-vendidos/<CAT_ID>` (o
  `mercadolivre.com.br/mais-vendidos/<CAT_ID>` en Brasil) → devuelve un
  listado ya rankeado de los productos más vendidos de esa categoría exacta.
- El `CAT_ID` tiene que ser un ID real de la taxonomía de ML
  (`MLA…`=Argentina, `MLB…`=Brasil, `MLM…`=México, `MLU…`=Uruguay).

**No se puede (con este enfoque):**
- Búsqueda libre por texto a nivel producto (no hay endpoint público
  equivalente al buscador interno).
- Filtros de precio, marca, envío, etc. — la página de "más vendidos" no los
  admite, se scrapea tal cual la devuelve ML.
- Paginación: la página muestra un **techo fijo** (~20 productos); no hay
  "página 2" de más vendidos.
- Categorías inventadas o IDs de otro nivel de taxonomía que no exista en el
  país pedido → no matchea nada (ver resolver cross-país).

### 2.3 Amazon: no hay página nativa de "más vendidos por categoría"
- Se emula buscando el **nombre** de la categoría en el buscador normal y
  aplicando el parámetro de orden `s=exact-aware-popularity-rank` (el mismo
  que usa el dropdown "Los más vendidos"/"Best Sellers" del sitio).
- Techo: solo la **primera página** de resultados (típicamente entre ~16 y
  ~60 tarjetas según el layout que devuelva Amazon ese día).
- Como se busca por nombre y no por ID de categoría real, nombres ambiguos
  (ej. "Notebooks") pueden traer resultados de otro rubro.

### 2.4 Anti-bot concreto de cada sitio
| Sitio | Sistema | Cómo se evade en este proyecto |
|---|---|---|
| MercadoLibre | DataDome (BotManager) | `curl_cffi impersonate="chrome"` + resolución del proof-of-work SHA256 (cookies `_bmstate`/`_bmc`/`_bm_skipml`) |
| Amazon | "Robot Check" / captcha propio | `curl_cffi impersonate="chrome"` + cookies de locale (`i18n-prefs`, `lc-main`) + warm-up a la home antes de buscar |

Ninguno de los dos motores resuelve **CAPTCHA visual** — si aparece, el
request se cuenta como bloqueado y se reintenta con backoff; no hay bypass.

### 2.5 Cobertura de categorías entre países (solo ML)
| País | Cobertura de matcheo desde AR |
|---|---|
| Uruguay | ~93% |
| México | ~87% |
| Brasil | ~76% |

Lo que no matchea no se inventa: la columna avisa "sin categoría
equivalente" (ver `resolver_equivalente` en `api.py`).

### 2.6 Localización obligatoria
- Precio y moneda dependen de cookies/headers correctos por país
  (`Accept-Language`, `i18n-prefs`, `lc-main` en Amazon). Sin esto, la
  respuesta puede venir en USD/inglés aunque se pida México o India.

---

## 3. Limitaciones y tiempos exactos de ESTE proyecto

### 3.1 Timeouts, reintentos y backoff (valores reales del código)

| Motor | Modo | Timeout/request | `max_retries` | Backoff (fórmula `min(base*intento, max)`) | Peor caso (solo backoff, sin contar red) |
|---|---|---|---|---|---|
| ML (`meli_fetch.obtener_html`) | **API** (`api.py`) | 30s | 2 | base=4 / max=6 → 4s, 6s | ~10s (según comentario del código: "falla rápido") |
| ML (`meli_fetch.obtener_html`) | **Lote/CLI** (`scraper_l1.py`, defaults) | 30s | 4 | base=8 / max=24 → 8s, 16s, 24s, 24s | ~72s + reintentos de red |
| Amazon (`amazon_fetch.buscar`) | **API** (`api.py`) | 30s (×2 por intento: warm-up + búsqueda) | 3 | base=5 / max=15 → 5s, 10s, 15s | ~30s de backoff (+ hasta 180s si cada request agota timeout) |
| Amazon (`amazon_fetch.buscar`) | **Default de la función** | 30s | 2 | base=4 / max=8 → 4s, 8s | ~12s |

- **Proof-of-Work de ML**: fuerza bruta de SHA256 (`solve_pow`), costo
  variable según la dificultad que mande DataDome ese momento; en la
  práctica, milisegundos a pocos segundos. No hay techo de tiempo puesto por
  el código — si la dificultad sube mucho, puede demorar más (riesgo latente
  no cubierto).
- **Detección de bloqueo Amazon**: `esta_bloqueado(html)` (por palabras clave
  de captcha) **o** `len(html) < 50000` (página sospechosamente corta/parcial).
- **Detección de bloqueo ML**: presencia de marcadores en el HTML
  (`suspicious-traffic`, `verifyChallenge`, `account-verification`,
  `micro-landing-container`) — no hay chequeo por longitud.
- Si tras los reintentos sigue bloqueado, la API responde **HTTP 503** al
  frontend (no cuelga esperando indefinidamente).

### 3.2 Caché en memoria — no persistente, no compartida
- `_cache` es un **diccionario en RAM** dentro del proceso de `api.py`, TTL
  fijo `CACHE_TTL_S = 600` (10 min), para ambos motores (ML por `cat_id`,
  Amazon por clave `AMZ:<site>:<query>`).
- **Se pierde por completo** al reiniciar el proceso (no hay disco/DB detrás).
- **No se comparte** entre instancias: si algún día se corre más de un
  worker/proceso de `uvicorn`, cada uno tiene su propia caché — no hay Redis
  ni nada equivalente.

### 3.3 Concurrencia: solo protegida por categoría/query, no en global
- `_lock_de(key)` da un lock **por clave** (`threading.Lock`), así que la
  *misma* categoría o búsqueda Amazon nunca se scrapea dos veces en paralelo.
- Pero **no hay límite global**: si el frontend pide 4 países × varias
  fuentes Amazon a la vez (como hace al tocar "Iniciar búsqueda"), todas esas
  claves distintas scrapean **en simultáneo**, sin ningún throttle agregado.
  Esto es exactamente el patrón de riesgo descrito en §1.8: cuantas más
  fuentes se seleccionen a la vez, más chance de que DataDome/Amazon
  empiecen a bloquear por comportamiento agregado.
- El techo real de "cuántos requests simultáneos soporta el proceso" no está
  fijado por este código: lo pone el pool de threads por defecto que usa
  Starlette/anyio para correr los endpoints síncronos (no hay `--workers` ni
  límite de concurrencia configurado explícitamente en `api.py`).

### 3.4 Sin autenticación ni rate-limit propio en la API
- CORS abierto (`allow_origins=["*"]`) y **sin API key, sin límite de
  requests por IP/usuario**. Cualquiera con la URL puede pegarle a
  `/mas-vendidos-pais` o `/amazon` tantas veces como quiera.
- Esto significa que el propio proyecto **no protege a MercadoLibre/Amazon
  de un uso abusivo** desde tu URL pública — el único freno es la caché de
  10 min. Si se publica la URL ampliamente, hay riesgo de auto-generar el
  bloqueo por volumen (ver §1.8).

### 3.5 Techo de datos por diseño (no es un bug, es el límite de la fuente)
- ML: máximo los productos que la página `/mas-vendidos/<id>` renderiza
  (normalmente ~20), sin stock, sin variantes, sin historial de precio.
- Amazon: solo la primera página de resultados de búsqueda con el filtro de
  orden aplicado (sin paginación implementada).
- No hay endpoint de detalle de producto individual en ninguno de los dos
  motores — solo el listado.

### 3.6 Dependencia de infraestructura local
- El backend necesita correr en una PC con **IP residencial** encendida
  (§1.2 aplicado a este proyecto). No se puede mover a Render/Railway/VPS sin
  perder la evasión de DataDome.
- El túnel gratuito de Cloudflare (`cloudflared.exe`) da una URL **efímera**
  que cambia cada reinicio y puede cortarse sin aviso — no tiene SLA. Ver
  `mantener_online.ps1` como mitigación parcial (auto-restart), no como
  solución definitiva.

### 3.7 Selectores hardcodeados = fragilidad ante rediseños
- `meli_common.parsear_productos` y `amazon_fetch.parsear_resultados`
  dependen de clases CSS específicas (`poly-card`, `s-search-result`, etc.).
  Un cambio de layout en ML o Amazon puede dejar de parsear productos de un
  día para el otro sin ningún error explícito (devuelve lista vacía →
  estado `"vacio"`), hay que estar atento a ese estado en producción.

### 3.8 Sin resolución de CAPTCHA integrada al flujo automático
- El único camino con navegador real (`scraper_browser.py`, Selenium) es un
  script aparte, **no** conectado a `api.py`. Si el proof-of-work de
  DataDome no alcanza y aparece un captcha visual real, la API no tiene cómo
  resolverlo sola: el usuario ve el error 503 y tiene que reintentar más
  tarde o correr el fallback manual.
