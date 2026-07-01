# App Más Vendidos MELI — Cómo levantarla y publicarla

La web (`htmlMvpNuevosNegociosAI.html`) trae **productos reales** de MercadoLibre
(AR / MX / UY / BR) desde el backend FastAPI que está en `Scrapper Meli L1/`.

> **Clave:** el backend ahora **sirve también la web**. Así hay **una sola URL**
> para todo (sin CORS, sin pegar `?api=`). El HTML detecta solo a qué backend
> pegarle: si se abre desde una URL http(s) usa ese mismo origen; si se abre como
> archivo local usa `http://127.0.0.1:8000`.

---

## Publicar para que la use CUALQUIERA (1 clic)

En la carpeta `Scrapper Meli L1/`:

```text
Doble clic en  PUBLICO.bat
```

Abre dos ventanas:
1. **Backend Meli** — el servidor (puerto 8000) que además sirve la web.
2. **Túnel Cloudflare** — imprime una URL pública tipo
   `https://XXXX-XXXX.trycloudflare.com`.

Esa URL es la que compartís. **Cualquiera la abre y usa la app** (elige categoría,
fuentes y "Iniciar búsqueda" → productos reales). Mientras esas dos ventanas estén
abiertas y tu PC encendida, funciona desde cualquier lado.

> El backend corre en tu PC a propósito: tu **IP residencial** no la bloquea ML.
> Hosting cloud común (Render/Railway/VPS) usa IPs de datacenter que ML bloquea.

### Detalles importantes
- La URL gratis del túnel **cambia cada vez** que reabrís `PUBLICO.bat`.
- Si cerrás las ventanas (o apagás/suspendés la PC), la app deja de estar online.
- El backend **cachea 10 min** por categoría: la 2ª consulta es instantánea.

---

## Uso solo LOCAL (en tu PC, sin internet)

**Como un programa de escritorio (recomendado):**

```text
1. Doble clic (una sola vez)  en  "Crear Acceso Directo.bat"
2. De ahi en mas, doble clic en  "Iniciar App.lnk"  (icono propio)
```

`Iniciar App.lnk` corre `Iniciar App.vbs`, que **no muestra ninguna ventana
de CMD**: instala dependencias si faltan, levanta el backend oculto (o
detecta que ya está corriendo, sin duplicarlo) y en **todos los casos abre
el navegador** con la app en `http://127.0.0.1:8000/`. Para cerrarla, doble
clic en `Detener App.vbs`.

**Con la consola visible (para debug):**

```text
Doble clic en  start.bat
```

Mismo resultado (instala dependencias, levanta backend+web, abre navegador)
pero mostrando la ventana con los logs — útil si algo falla y `Iniciar
App.vbs` solo te muestra un cartel de error genérico.

Si preferís hacerlo a mano: `py -m pip install -r requirements.txt` y luego
`py -m uvicorn api:app --host 0.0.0.0 --port 8000`, y abrís
`http://127.0.0.1:8000/` en el navegador. También podés abrir el archivo
`htmlMvpNuevosNegociosAI.html` directo (apunta a `localhost` solo).

---

## URL fija (opcional, recomendado si lo vas a usar seguido)

Para que la URL **no cambie**, creá un *named tunnel* (necesitás cuenta Cloudflare
gratis + un dominio en Cloudflare):

```powershell
cloudflared tunnel login
cloudflared tunnel create meli
cloudflared tunnel route dns meli app.tudominio.com
cloudflared tunnel run --url http://localhost:8000 meli
```

Queda fijo en `https://app.tudominio.com` (web + API en la misma URL).

---

## Cobertura del mapeo entre países

AR 100% · UY ~90% · MX ~85% · BR ~50% (Brasil está en portugués, matchea menos).
Donde una categoría no existe en un país, esa columna lo avisa en vez de romperse.

## Endpoints del backend
`GET /` (la web) · `/health` · `/arbol?pais=` · `/categorias?pais=&nivel=` ·
`/mas-vendidos/{id}` · `/mas-vendidos-pais?ref=&pais=` · `/api` (info).
