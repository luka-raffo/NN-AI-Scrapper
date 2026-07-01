# NN AI — Scrapper Más Vendidos MercadoLibre

Herramienta interna para explorar las categorías de MercadoLibre y traer, a
demanda, el ranking de **productos más vendidos** de una categoría en
**Argentina, México, Uruguay y Brasil**, comparándolos lado a lado.

## ¿Qué hay acá?

```
Recursos/
├─ htmlMvpNuevosNegociosAI.html   ← la web (UI + JS, sin frameworks)
├─ DOCUMENTACION_TECNICA.md       ← cómo funciona todo (LEER ESTO)
├─ INTEGRACION.md                 ← cómo levantarla y publicarla
└─ Scrapper Meli L1/
   ├─ api.py                      ← backend FastAPI (sirve la web + API + resolver)
   ├─ meli_fetch.py / meli_common.py  ← motor de scraping (curl_cffi + DataDome)
   ├─ categorias_*.json           ← catálogos por país (~12k categorías c/u)
   └─ *.bat / mantener_online.ps1 ← scripts de arranque
```

> **Documentación completa:** [Recursos/DOCUMENTACION_TECNICA.md](Recursos/DOCUMENTACION_TECNICA.md)
> **Limitaciones del scraping (general → específico de este proyecto):** [Recursos/LIMITACIONES_SCRAPING.md](Recursos/LIMITACIONES_SCRAPING.md)

## Levantar rápido (local) — front + back en un solo paso

El backend sirve la web (front) directamente, así que **no hay que levantar
nada por separado**: un solo proceso corre las dos cosas.

### Opción 1 — un doble clic, como cualquier programa (recomendada)

1. Instalá [Python 3](https://www.python.org/downloads/) si no lo tenés
   (al instalar, tildá **"Add python.exe to PATH"**).
2. Entrá a `Recursos/Scrapper Meli L1/` y hacé doble clic **una sola vez** en
   `Crear Acceso Directo.bat` — crea el ícono **`Iniciar App.lnk`** (con el
   logo de la app) en esa misma carpeta.
3. De ahí en adelante, usá **ese ícono** para abrir la app: **no se ve
   ninguna ventana de CMD** — queda corriendo oculto e **abre el navegador
   solo** en `http://127.0.0.1:8000/`, en **cada click** (si ya estaba
   corriendo, no lo vuelve a levantar; solo reabre el navegador).
4. Para cerrarla: doble clic en `Detener App.vbs` (misma carpeta).

Si algo falla (p. ej. Python no instalado), como no hay ventana visible se
muestra un cartel de error con la indicación de correr `start.bat` para ver
el detalle. `start.bat` sigue disponible tal cual estaba: igual que la
opción de arriba pero con la consola visible (útil para diagnosticar).

### Opción 2 — manual (PowerShell/CMD)

```powershell
cd "Recursos/Scrapper Meli L1"
py -m pip install -r requirements.txt
py -m uvicorn api:app --host 0.0.0.0 --port 8000
```

Abrí http://127.0.0.1:8000/ — la web se sirve desde el backend.

> Requisito único: **Python 3.9+** instalado. No hace falta Node, npm ni
> ningún otro runtime — el front es HTML/JS plano sin build.

## Publicar en internet

Doble clic en `Recursos/Scrapper Meli L1/PUBLICO.bat` (backend + túnel Cloudflare),
o `MANTENER ONLINE.bat` para que se mantenga solo. Detalle en
[INTEGRACION.md](Recursos/INTEGRACION.md).

> **Por qué corre en una PC y no en la nube:** MercadoLibre (DataDome) bloquea las
> IPs de datacenter. Solo funciona confiable desde una **IP residencial**, por eso
> el backend corre localmente y se expone con un túnel.

## No incluido en el repo (por tamaño)

- `HTTP_Request *.json` (~45MB c/u): dumps crudos de la API de categorías.
  El derivado liviano (`categorias_*.json`) sí está versionado.
- `cloudflared.exe`: descargar de https://github.com/cloudflare/cloudflared/releases
