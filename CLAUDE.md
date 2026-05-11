# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Proyecto

Agente de búsqueda de productos y gestión de campañas para e-commerce en Uruguay.
Stack: FastAPI + Claude API (Anthropic) + SQLite (dev) / PostgreSQL Neon (prod) + MercadoLibre API.

## Comandos

### Backend

```bash
# Instalar dependencias
cd backend && pip install -r requirements.txt

# Levantar el servidor de desarrollo
cd backend && uvicorn main:app --reload

# El servidor queda en http://localhost:8000
# La DB se crea automáticamente en backend/opherabeauty.db al arrancar
```

El archivo `backend/.env` debe tener:
```
ANTHROPIC_API_KEY=sk-ant-...
# Opcional: para usar PostgreSQL en lugar de SQLite local
DATABASE_URL=postgresql://...
```

### Frontend

Abrir los archivos HTML en `Pagina/` directamente en el navegador. Por defecto apuntan a `http://localhost:8000`.

### Deploy (Vercel)

El punto de entrada para Vercel es `api/index.py`, que importa la `app` de `backend/main.py`. La configuración de rutas y builds está en `vercel.json`. En producción se usa `DATABASE_URL` (Neon/PostgreSQL); si no está definida, cae a SQLite local.

## Arquitectura

```
Pagina/
  index.html              — Landing page OpheraBeauty
  dashboard.html          — Dashboard principal (sidebar drawer mobile, chat, notas, campañas)
  agente_productos.html   — Agente buscador de productos (usa /api/agent/buscar-productos)
  sourcing_lab.html       — Sourcing Lab: comparativo de proveedores por país (CRUD, dinámico, DB)
  login.html              — Login
backend/
  main.py                 — FastAPI: todos los endpoints + system prompt del agente
  database.py             — SQLAlchemy: modelos y configuración de DB (SQLite/PostgreSQL)
  requirements.txt        — Dependencias Python
  .env                    — Variables de entorno (no commitear)
  opherabeauty.db         — SQLite DB (se crea automáticamente, no commitear)
api/
  index.py                — Punto de entrada para Vercel (importa app de backend/main.py)
vercel.json               — Configuración de rutas y builds para Vercel
```

## Mobile Responsive

Todas las páginas son mobile-responsive (breakpoint principal: 768px).

**Patrón de sidebar (dashboard.html, sourcing_lab.html, agente_productos.html):**
- Desktop: sidebar fijo 240px a la izquierda + área de contenido fluida
- Mobile: sidebar se convierte en drawer lateral (`position:fixed; transform:translateX(-105%)`)
  - `.open` → `transform:translateX(0)`
  - Botón hamburger (☰) en la topbar, visible solo en mobile
  - Backdrop overlay semitransparente para cerrar el drawer al tocar fuera
  - JS: `toggleSidebar()` / `closeSidebar()`, cierre automático al navegar

**Sourcing Lab (sourcing_lab.html) — detalles adicionales:**
- KPI strip pasa a 2 columnas en mobile
- Cards de productos en columna única en mobile
- Formulario modal se adapta a pantalla completa en mobile
- Dropdown de país (12 opciones) auto-rellena moneda y tipo de cambio (`data-bandera`, `data-moneda`, `data-tc`)
- Preview en tiempo real de `costo_total_uyu` y `margen_pct` mientras se edita el formulario

## Base de Datos

`database.py` usa `DATABASE_URL` del entorno. Si no existe, usa SQLite (`backend/opherabeauty.db`). Las tablas se crean automáticamente en el startup de FastAPI (`init_db()`).

### Tablas

| Tabla               | Descripción                                          |
|---------------------|------------------------------------------------------|
| `products`          | Catálogo de productos (activos, en análisis, etc.)   |
| `product_searches`  | Historial de búsquedas del agente (auto-guardado)    |
| `campaigns`         | Campañas de Meta Ads                                 |
| `campaign_metrics`  | Métricas diarias por campaña                         |
| `business_notes`    | Decisiones y notas del negocio                       |
| `sourcing_items`    | Comparativo de proveedores por país (Sourcing Lab)   |

### Campos clave de `products`
`nombre`, `categoria`, `url_alibaba`, `url_aliexpress`, `costo_usd`, `precio_venta_uyu`,
`margen` (calculado automático: `precio_venta_uyu / (costo_usd * 43)`), `stock`,
`estado` (en_analisis|activo|pausado|descartado), `puntaje` (1-10),
`speech`, `analisis`, `riesgo`, `termino_busqueda`, `termino_ml`

### Campos clave de `sourcing_items`
`producto`, `pais_origen`, `bandera` (emoji), `moneda`, `precio_origen`, `tipo_cambio_uyu`,
`peso_kg`, `fuente`, `costo_envio_uyu`, `precio_mercado_uy`, `precio_venta_sugerido`.
El endpoint serializa campos calculados: `costo_origen_uyu`, `costo_total_uyu`, `margen_pct`.

## Endpoints del backend

### Agente y búsqueda (existentes)
- `GET  /`                                  — Health check
- `POST /api/chat`                          — Chat con el agente OpheraBeauty
- `POST /api/agent/buscar-productos`        — Busca productos con Claude (auto-guarda en DB)
- `GET  /api/ml/precios?q=...`             — Proxy MercadoLibre UY

### Productos
- `GET    /api/products`                    — Lista catálogo (filtro: ?estado=activo)
- `POST   /api/products`                    — Agrega producto manualmente
- `GET    /api/products/{id}`               — Detalle de un producto
- `PATCH  /api/products/{id}`               — Actualiza producto (stock, precio, estado, etc.)
- `POST   /api/products/from-search/{search_id}/{index}` — Guarda producto de una búsqueda al catálogo

### Búsquedas (historial)
- `GET  /api/searches`                      — Historial de búsquedas (últimas 20)
- `GET  /api/searches/{id}`                 — Resultado completo de una búsqueda

### Campañas
- `GET    /api/campaigns`                   — Lista campañas
- `POST   /api/campaigns`                   — Crea campaña
- `PATCH  /api/campaigns/{id}`              — Actualiza campaña (estado, copy, IDs de Meta, etc.)

### Métricas de campaña
- `GET  /api/campaigns/{id}/metrics`        — Métricas históricas de una campaña
- `POST /api/campaigns/{id}/metrics`        — Agrega métricas del día

### Notas de negocio
- `GET    /api/notes`                       — Lista notas (filtro: ?tag=pricing)
- `POST   /api/notes`                       — Crea nota
- `DELETE /api/notes/{id}`                  — Elimina nota

### Sourcing Lab
- `GET    /api/sourcing`                    — Lista ítems (filtros: ?categoria= ?pais=)
- `POST   /api/sourcing`                    — Crea ítem de comparativo
- `PATCH  /api/sourcing/{id}`               — Actualiza ítem
- `DELETE /api/sourcing/{id}`               — Elimina ítem

## Estructura del JSON de producto (agente)

Campos: `nombre`, `categoria`, `puntaje` (1-10), `costo_estimado_usd`,
`precio_venta_sugerido_uyu`, `margen` (multiplicador), `termino_busqueda` (inglés, AliExpress),
`termino_ml` (español, MercadoLibre UY), `analisis`, `speech`, `riesgo`, `riesgo_detalle`.

El frontend también soporta campos legacy: `costo_proveedor` y `precio_venta_sugerido`.
