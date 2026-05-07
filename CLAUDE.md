# CLAUDE.md — OpheraBeauty E-Commerce UY

## Proyecto

Agente de búsqueda de productos y gestión de campañas para e-commerce en Uruguay.
Stack: FastAPI + Claude API (Anthropic) + SQLite + MercadoLibre API.

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

El archivo `.env` dentro de `backend/` debe tener:
```
ANTHROPIC_API_KEY=sk-ant-...
```

### Frontend

Abrir los archivos HTML directamente en el navegador. Por defecto apuntan a `http://localhost:8000`.

## Arquitectura

```
index.html                — Landing page OpheraBeauty
dashboard.html            — Dashboard principal
agente_productos.html     — Agente buscador de productos
login.html                — Login
backend/
  main.py                 — FastAPI: todos los endpoints
  database.py             — SQLAlchemy: modelos y configuración de DB
  requirements.txt        — Dependencias Python
  .env                    — API key de Anthropic (no commitear)
  opherabeauty.db         — SQLite DB (se crea automáticamente, no commitear)
```

## Base de Datos (SQLite — opherabeauty.db)

### Tablas

| Tabla               | Descripción                                          |
|---------------------|------------------------------------------------------|
| `products`          | Catálogo de productos (activos, en análisis, etc.)   |
| `product_searches`  | Historial de búsquedas del agente (auto-guardado)    |
| `campaigns`         | Campañas de Meta Ads                                 |
| `campaign_metrics`  | Métricas diarias por campaña                         |
| `business_notes`    | Decisiones y notas del negocio                       |

### Campos clave de `products`
`nombre`, `categoria`, `url_alibaba`, `url_aliexpress`, `costo_usd`, `precio_venta_uyu`,
`margen` (calculado automático), `stock`, `estado` (en_analisis|activo|pausado|descartado),
`puntaje` (1-10), `speech`, `analisis`, `riesgo`, `termino_busqueda`, `termino_ml`

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

## Estructura del JSON de producto (agente)

Campos: `nombre`, `categoria`, `puntaje` (1-10), `costo_estimado_usd`,
`precio_venta_sugerido_uyu`, `margen` (multiplicador), `termino_busqueda` (inglés, AliExpress),
`termino_ml` (español, MercadoLibre UY), `analisis`, `speech`, `riesgo`, `riesgo_detalle`.

El frontend también soporta campos legacy: `costo_proveedor` y `precio_venta_sugerido`.
