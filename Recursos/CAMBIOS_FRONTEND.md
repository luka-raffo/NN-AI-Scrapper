# Cambios en el Frontend - Mejoras de Layouts de Productos

## Cambios Realizados

### 1. **Tamaño consistente de las tarjetas de productos**
- **Línea 1147**: Cambié `min-height:300px` por `height:300px` en la clase base `.product-card`
- Esto asegura que TODAS las tarjetas de productos tengan exactamente la misma altura (300px), sin importar el contenido
- Antes: las tarjetas crecían según su contenido (variable)
- Después: las tarjetas tienen altura fija y uniforme (300px exactos)

### 2. **Scroll dentro del contenedor de productos (Multiple cambios)**

#### 2a. Media query pantalla grande (≥901px) - Línea 1402-1427:
   - Cambié `.market-column__list` de `overflow:visible` a `overflow:auto`
   - Cambié de `max-height:none` a `max-height:calc(100vh - 370px)` para proporcionar un límite de altura
   - Agregué estilos visibles al scrollbar (width:5px, colores sutiles)

#### 2b. Estilos globales - Línea 1485-1497:
   - Actualicé la definición global de `.market-column__list` para mantener scroll por defecto
   - Cambié de `max-height:none !important; overflow:visible !important;` 
   - A `max-height:calc(100vh - 370px); overflow:auto;`
   - Agregué una media query interna para pantalla pequeña que restaura `overflow:visible`

### 3. **Scroll único para todas las columnas (V28)**

- **Problema:** V27 ponía un scrollbar por columna; el usuario quiere UN solo scrollbar que mueva todas las columnas juntas.
- **Solución (bloque CSS V28, ≥901px):**
  - `#searchView .results-scroll` → `overflow-y: auto` (UN scrollbar vertical acá)
  - `#searchView .market-results-grid` → `height: auto; align-items: start` (crece con el contenido)
  - `#searchView .market-column` → `height: auto; overflow: visible; contain: none` (sin scroll propio)
  - `#searchView .market-column__head` → `position: sticky; top: 0; z-index: 2` (sticky al hacer scroll)
  - `#searchView .market-column__list` → `overflow-y: visible; height: auto` (se expande libre)

## Resultado Visual
- ✅ Las columnas (AR, MX, UY, BR / Amazon) tienen tarjetas de tamaño uniforme (300px)
- ✅ **Un único scrollbar vertical** en el contenedor de resultados mueve todas las columnas juntas
- ✅ Las cabeceras de cada país permanecen **sticky** (siempre visibles al scrollear)
- ✅ Header y panel de categorías siempre visibles (viewport bloqueado)
- ✅ Scroll horizontal si hay más columnas que espacio disponible

### 4. **Alineación de cards + posición del toggle (V29)**

**Problema 1 — cards desalineadas:** Línea ~2053 tenía `height:auto !important; min-height:354px !important` que pisaba el `height:300px` base, haciendo que cada card creciera a distinta altura.
- Fix: `height:300px !important; min-height:300px !important` en V29.

**Problema 2 — botón toggle en el centro de la pantalla:** V27 puso `position:static !important` en `.sidebar-rail`. El botón `.sidebar-toggle` es `position:absolute` y usa `.sidebar-rail` como contexto de posicionamiento; al volverse `static`, el botón se ancló al `<body>` → centro de pantalla.
- Fix: `.sidebar-rail { position:relative !important }` en V29.

**Problema 3 — cabeceras de columna de altura variable:** Si `.market-column__head` tiene distinta altura en cada columna, las cards no arrancan en el mismo Y.
- Fix: `height:62px !important; flex-shrink:0 !important` en `.market-column__head`.

### 5. **Cards más compactas e imágenes más grandes (V30)**

**Pedido:** imágenes visualmente más grandes dentro de la card, y ver más productos en pantalla sin hacer zoom out.

**Cards:** reducidas de 300px → 230px (~23% más compactas, ~30% más cards visibles en el viewport).

**Imagen:** contenedor `.product-card__media` pasa de 132px a 115px, pero al mismo tiempo el padding de la imagen se reduce de 15px → 8px. El efecto combinado es que:
- La imagen ocupa el 50% de la card (antes 44%) → proporcionalmente más grande
- El contenido de la imagen tiene más píxeles visibles (menos espacio desperdiciado en padding)

**Body:** `padding` reducido a `6px 10px 5px` (era `10px 11px 11px`), `gap` a `4px` (era `7px`), `font-size` del precio a `14px` (era `17px`), `min-height` del título a `0` (era `36px`), cuotas y envío ocultos con `display:none`.

**Resultado neto:** imagen visible 155px vs 107px original = **45% más grande en píxeles absolutos**.

### 6. **Header compacto + no-cache en servidor (V31)**

**Pedido:** header más pequeño para ver más cards en pantalla. Referencia: archivo `nuevos_negocios_ai_productos_ecommerce_v25_compact_results_header.html`.

**Header:** reducido de 92px → 64px (−28px = ~30% más compacto):
- `.header-subtitle` oculto (`display:none`)
- `.tool-mark` / img: 76px → 44px
- `.brand-logo`: 172px → 148px
- `.header-separator`: height → 36px
- `.workspace`, `.category-explorer`, `.sidebar-rail`: todos recalculados con `calc(100dvh - 64px)`

**Efecto:** con el header más chico y las cards de 240px (V30), se ven aproximadamente 2 filas más de cards que con el diseño original (92px header + 300px cards).

**api.py:** `FileResponse` reemplazado por `HTMLResponse` con `Cache-Control: no-store`. Ahora el browser nunca cachea el HTML → cualquier cambio de CSS se ve con un simple `F5` (sin necesidad de Ctrl+Shift+R).

### 7. **Header ultra-compacto en búsqueda activa + imágenes más grandes + limpieza de títulos (V32)**

**Pedido:** header mucho más chico al buscar, eliminar textos "Resultados de búsqueda" / "Top 20 por e-commerce" / "X fuentes", e imágenes de productos más grandes.

**Header dinámico:**
- Clase `is-searched` en `<body>` se activa cuando `state.hasSearched = true` (toggle en `renderResults()`).
- Con la clase activa, el header baja de 64px → **42px** (−22px adicionales).
- Se ocultan: `.tool-mark` y `.header-eyebrow`.
- Logo reducido a 108px, título a 14px, `header-context` con padding mínimo.
- `.workspace`, `.category-explorer` y `.sidebar-rail` recalculados con `calc(100dvh - 42px)`.
- Transición suave `min-height .2s ease` al activarse.

**Imágenes más grandes (V30 actualizado):**
- `.product-card`: 240px → **280px**
- `.product-card__media`: 155px → **190px** (+35px, ~22% más grande)
- El body de la card mantiene ~90px para precio y título.

**Limpieza de UI (HTML):**
- Eliminado `<p class="results-eyebrow">Resultados de búsqueda</p>`
- Eliminado `<h3 class="results-title">Top 20 por e-commerce</h3>`
- Eliminado `<div id="resultsMeta">` (mostraba "X fuentes seleccionadas")
- Las referencias JS a `resultsMeta` ya estaban guardadas con `if (meta)`, sin cambios necesarios.

### 8. **Branding Bidcom: Nueva paleta de color + tipografía Montserrat (V33)**

**Paleta principal (tonos azul base):**
- `#00006F` Azul Noche — fondos profundos, textos de énfasis
- `#000091` Azul Marino — colores activos, botones oscuros
- `#0000D4` Azul Medio — acento principal, bordes de selección
- `#0000FF` Azul Eléctrico — estados hover intensos
- `#0051FF` Azul Vibrante — gradiente final del header y botones

**Paleta secundaria (contraste y acento):**
- `#00A1FF` Azul Cian — reemplaza al amarillo `#ffc20e` como color de acento/destaque
- `#5300FF` Violeta Azulado — variable disponible para badges especiales
- Rank badges: fondo Cian `#00A1FF` para principal, Marino `#000091` para secundario

**Tipografía:**
- Google Fonts importadas: **Montserrat** (400–900) + **Open Sans** (400–700)
- `font-family` del body: `'Montserrat', 'Open Sans', Inter, ...`

**Elementos actualizados:**
- `:root` CSS variables (`--bidcom-blue`, `--bidcom-blue-dark`, `--bidcom-blue-deep`, `--yellow`, `--active-blue`) + variables nuevas (`--bidcom-electric`, `--bidcom-vibrant`, `--bidcom-cyan`, `--bidcom-indigo`)
- Header gradient: `#00006F → #0000D4 → #0051FF` + radial glow Cian
- Header dot accent: `#ffc20e → #00A1FF` (Cian) con glow `rgba(0,161,255,.22)`
- Botón "Iniciar búsqueda": gradiente `#00006F → #000091 → #0000D4`
- Botón "Sourcing": gradiente `#000091 → #0051FF`
- Column headers de productos: fondo `#eeeeff → #f0f0ff` (azul lavanda suave)
- Tree row seleccionado: fondo `#eeeeff → #f5f5ff`, borde izquierdo `#0000D4`
- Dropdown opciones activas: fondo `#eeeeff`, borde `#0000D4`
- Precio de producto: `#00006F`
- Explorer title: `#00006F`

### 9. **Results Head adaptativo: título + contexto por estado del panel (V34)**

**Pedido:** en el header de las cards siempre mostrar "Top 20 por e-commerce" y el número de fuentes; mostrar Branch ML + Categoría Bidcom solo cuando el panel superior esté colapsado (y posicionar título a la derecha en ese caso).

**Lógica de layout (bloque CSS V34, ≥901px):**

| Estado del panel superior | Izquierda | Derecha |
|---|---|---|
| Expandido (visible) | RESULTADOS DE BÚSQUEDA · Top 20 · X fuentes | — (contexto oculto, se ve arriba) |
| Colapsado (`body.top-panel-collapsed`) | Branch ML seleccionada + Categoría Bidcom | RESULTADOS DE BÚSQUEDA · Top 20 · X fuentes |

**Implementación:**
- `order:0` en `.results-head-left` por defecto → `order:1` cuando colapsado
- `order:0` en `.results-context-summary` siempre → `display:none !important` por defecto, `display:grid !important` cuando `body.top-panel-collapsed`
- `justify-content:flex-start` por defecto → `space-between` cuando colapsado
- El elemento `#resultsMeta` fue restaurado al HTML → el JS ya lo actualiza (`"X fuentes"`, `"buscando…"`, etc.)

**HTML modificado:** `results-head` ahora contiene `.results-head-left` (eyebrow + title + meta) + `#resultsContextSummary` (Branch + Bidcom blocks).

## Archivos Modificados
- `htmlMvpNuevosNegociosAI.html` - CSS de layout y dimensiones
- `Scrapper Meli L1/api.py` - no-cache headers para desarrollo sin fricción
