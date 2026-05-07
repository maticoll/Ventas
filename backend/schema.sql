-- ============================================================
-- OpheraBeauty — Schema para Supabase (PostgreSQL)
-- Correr en: Supabase > SQL Editor > New query
-- ============================================================


-- ── 1. Catálogo de productos ─────────────────────────────────
CREATE TABLE IF NOT EXISTS products (
    id                  SERIAL PRIMARY KEY,
    nombre              VARCHAR(200)    NOT NULL,
    categoria           VARCHAR(100),
    url_alibaba         TEXT,
    url_aliexpress      TEXT,
    costo_usd           NUMERIC(10,2),
    precio_venta_uyu    NUMERIC(10,2),
    margen              NUMERIC(6,2),           -- multiplicador: precio / costo
    stock               INTEGER         DEFAULT 0,
    estado              VARCHAR(50)     DEFAULT 'en_analisis',
                                                -- en_analisis | activo | pausado | descartado
    puntaje             INTEGER,                -- score del agente 1-10
    speech              TEXT,                   -- copy de venta generado
    analisis            TEXT,                   -- análisis del agente
    riesgo              VARCHAR(50),            -- Bajo | Medio | Alto
    notas               TEXT,
    termino_busqueda    VARCHAR(200),           -- búsqueda en AliExpress (inglés)
    termino_ml          VARCHAR(200),           -- búsqueda en MercadoLibre UY
    created_at          TIMESTAMPTZ     DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     DEFAULT NOW()
);


-- ── 2. Historial de búsquedas del agente ─────────────────────
CREATE TABLE IF NOT EXISTS product_searches (
    id                  SERIAL PRIMARY KEY,
    categoria           VARCHAR(100),
    margen_minimo       NUMERIC(4,1),
    cantidad            INTEGER,
    resultado_json      JSONB,                  -- array de productos devuelto por Claude
    total_resultados    INTEGER,
    created_at          TIMESTAMPTZ     DEFAULT NOW()
);


-- ── 3. Campañas de Meta Ads ───────────────────────────────────
CREATE TABLE IF NOT EXISTS campaigns (
    id                      SERIAL PRIMARY KEY,
    nombre                  VARCHAR(200)    NOT NULL,
    product_id              INTEGER         REFERENCES products(id) ON DELETE SET NULL,
    objetivo                VARCHAR(100)    DEFAULT 'TRAFFIC',
                                            -- TRAFFIC | CONVERSIONS | AWARENESS
    presupuesto_diario_usd  NUMERIC(8,2),
    audiencia_descripcion   TEXT,
    copy_headline           TEXT,
    copy_texto              TEXT,
    copy_cta                VARCHAR(100),
    estado                  VARCHAR(50)     DEFAULT 'borrador',
                                            -- borrador | activa | pausada | finalizada
    meta_campaign_id        VARCHAR(100),   -- ID de Meta Ads
    meta_adset_id           VARCHAR(100),
    meta_ad_id              VARCHAR(100),
    fecha_inicio            TIMESTAMPTZ,
    fecha_fin               TIMESTAMPTZ,
    notas                   TEXT,
    created_at              TIMESTAMPTZ     DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     DEFAULT NOW()
);


-- ── 4. Métricas diarias por campaña ──────────────────────────
CREATE TABLE IF NOT EXISTS campaign_metrics (
    id              SERIAL PRIMARY KEY,
    campaign_id     INTEGER         NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    fecha           DATE            NOT NULL,
    impresiones     INTEGER         DEFAULT 0,
    clicks          INTEGER         DEFAULT 0,
    ctr             NUMERIC(6,4)    DEFAULT 0,  -- click-through rate
    cpc             NUMERIC(8,4)    DEFAULT 0,  -- costo por click en USD
    gasto_usd       NUMERIC(10,2)   DEFAULT 0,
    alcance         INTEGER         DEFAULT 0,
    ventas          INTEGER         DEFAULT 0,
    roas            NUMERIC(8,4)    DEFAULT 0,  -- return on ad spend
    created_at      TIMESTAMPTZ     DEFAULT NOW(),
    UNIQUE(campaign_id, fecha)                  -- una fila por campaña por día
);


-- ── 5. Notas y decisiones del negocio ────────────────────────
CREATE TABLE IF NOT EXISTS business_notes (
    id          SERIAL PRIMARY KEY,
    tema        VARCHAR(200)    NOT NULL,
    duda        TEXT,
    conclusion  TEXT,
    contexto    JSONB,                          -- datos de respaldo (números, etc.)
    tags        VARCHAR(500),                   -- etiquetas separadas por coma
    created_at  TIMESTAMPTZ     DEFAULT NOW()
);


-- ── Índices para búsquedas frecuentes ────────────────────────
CREATE INDEX IF NOT EXISTS idx_products_estado         ON products(estado);
CREATE INDEX IF NOT EXISTS idx_products_categoria      ON products(categoria);
CREATE INDEX IF NOT EXISTS idx_campaigns_estado        ON campaigns(estado);
CREATE INDEX IF NOT EXISTS idx_campaigns_product_id    ON campaigns(product_id);
CREATE INDEX IF NOT EXISTS idx_metrics_campaign_fecha  ON campaign_metrics(campaign_id, fecha);
CREATE INDEX IF NOT EXISTS idx_searches_created        ON product_searches(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notes_created           ON business_notes(created_at DESC);


-- ── Trigger: updated_at automático ───────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE OR REPLACE TRIGGER trg_campaigns_updated_at
    BEFORE UPDATE ON campaigns
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
