"""
database.py — Capa de persistencia de OpheraBeauty
PostgreSQL (Neon) en producción / SQLite en desarrollo local

Tablas:
  products         — Catálogo de productos
  product_searches — Historial de búsquedas del agente
  campaigns        — Campañas de Meta Ads
  campaign_metrics — Métricas diarias por campaña
  business_notes   — Decisiones y notas del negocio
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, Column, Integer, Float, String, Text,
    DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

load_dotenv()

# ─── Configuración ────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Usa DATABASE_URL del entorno si existe (Neon/PostgreSQL),
# o cae a SQLite local para desarrollo
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{os.path.join(BASE_DIR, 'opherabeauty.db')}"
)

# connect_args solo necesario para SQLite
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ─── Modelos ──────────────────────────────────────────────────────────────────

class Product(Base):
    """
    Catálogo de productos — lo que venden o están evaluando vender.
    """
    __tablename__ = "products"

    id             = Column(Integer, primary_key=True, index=True)
    nombre         = Column(String(200), nullable=False)
    categoria      = Column(String(100))
    url_alibaba    = Column(Text)
    url_aliexpress = Column(Text)
    costo_usd      = Column(Float)           # costo de compra en USD
    precio_venta_uyu = Column(Float)         # precio de venta en pesos uruguayos
    margen         = Column(Float)           # multiplicador: precio_venta / costo
    stock          = Column(Integer, default=0)
    estado         = Column(String(50), default="en_analisis")
                                             # en_analisis | activo | pausado | descartado
    puntaje        = Column(Integer)         # 1-10, score del agente
    speech         = Column(Text)           # copy de venta generado por Claude
    analisis       = Column(Text)           # análisis del agente
    riesgo         = Column(String(50))     # Bajo | Medio | Alto
    notas          = Column(Text)           # notas manuales
    termino_busqueda = Column(String(200))  # término para AliExpress (en inglés)
    termino_ml     = Column(String(200))    # término para MercadoLibre UY

    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    campaigns      = relationship("Campaign", back_populates="product")


class ProductSearch(Base):
    """
    Historial de búsquedas del agente — cada vez que se buscan productos,
    se guarda la consulta y los resultados completos.
    """
    __tablename__ = "product_searches"

    id             = Column(Integer, primary_key=True, index=True)
    categoria      = Column(String(100))
    margen_minimo  = Column(Float)
    cantidad       = Column(Integer)
    resultado_json = Column(JSON)            # array de productos devuelto por Claude
    total_resultados = Column(Integer)
    created_at     = Column(DateTime, default=datetime.utcnow)


class Campaign(Base):
    """
    Campañas de Meta Ads — una por producto/objetivo.
    """
    __tablename__ = "campaigns"

    id                 = Column(Integer, primary_key=True, index=True)
    nombre             = Column(String(200), nullable=False)
    product_id         = Column(Integer, ForeignKey("products.id"), nullable=True)
    objetivo           = Column(String(100))   # TRAFFIC | CONVERSIONS | AWARENESS
    presupuesto_diario_usd = Column(Float)
    audiencia_descripcion  = Column(Text)      # descripción libre de la audiencia
    copy_headline      = Column(Text)
    copy_texto         = Column(Text)
    copy_cta           = Column(String(100))
    estado             = Column(String(50), default="borrador")
                                               # borrador | activa | pausada | finalizada
    meta_campaign_id   = Column(String(100))   # ID de Meta Ads (cuando se publica)
    meta_adset_id      = Column(String(100))
    meta_ad_id         = Column(String(100))
    fecha_inicio       = Column(DateTime)
    fecha_fin          = Column(DateTime)
    notas              = Column(Text)

    created_at         = Column(DateTime, default=datetime.utcnow)
    updated_at         = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    product            = relationship("Product", back_populates="campaigns")
    metrics            = relationship("CampaignMetrics", back_populates="campaign")


class CampaignMetrics(Base):
    """
    Métricas diarias de cada campaña — se actualiza desde Meta API.
    """
    __tablename__ = "campaign_metrics"

    id              = Column(Integer, primary_key=True, index=True)
    campaign_id     = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    fecha           = Column(DateTime, nullable=False)
    impresiones     = Column(Integer, default=0)
    clicks          = Column(Integer, default=0)
    ctr             = Column(Float, default=0.0)       # click-through rate %
    cpc             = Column(Float, default=0.0)       # costo por click en USD
    gasto_usd       = Column(Float, default=0.0)       # gasto total del día
    alcance         = Column(Integer, default=0)
    ventas          = Column(Integer, default=0)       # conversiones registradas
    roas            = Column(Float, default=0.0)       # return on ad spend

    created_at      = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    campaign        = relationship("Campaign", back_populates="metrics")


class SourcingItem(Base):
    """
    Comparativo de proveedores por país para el Sourcing Lab.
    Cada fila es un producto + origen (país proveedor).
    """
    __tablename__ = "sourcing_items"

    id                    = Column(Integer, primary_key=True, index=True)
    producto              = Column(String(200), nullable=False)   # nombre del producto
    marca                 = Column(String(100))                    # marca
    presentacion          = Column(String(100))                    # "50 ml", "300 ml", etc.
    categoria             = Column(String(100))                    # serum | limpiador | hidratante | etc.
    pais_origen           = Column(String(100), nullable=False)   # "Estados Unidos", "Brasil", etc.
    bandera               = Column(String(10))                     # emoji de bandera: 🇺🇸 🇧🇷 etc.
    moneda                = Column(String(10), default="USD")      # USD | BRL | ARS | EUR | etc.
    precio_origen         = Column(Float)                          # precio en moneda de origen
    tipo_cambio_uyu       = Column(Float)                          # tipo de cambio a UYU
    peso_kg               = Column(Float)                          # peso estimado en kg
    fuente                = Column(String(200))                    # proveedor / tienda
    costo_envio_uyu       = Column(Float, default=0)               # costo de envío en UYU
    precio_mercado_uy     = Column(Float)                          # precio referencia en Uruguay (UYU)
    precio_venta_sugerido = Column(Float)                          # precio de venta sugerido (UYU)
    notas                 = Column(Text)

    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BusinessNote(Base):
    """
    Decisiones y notas del negocio — el registro de todo lo que van
    resolviendo día a día (márgenes, precios, estrategias, dudas).
    """
    __tablename__ = "business_notes"

    id          = Column(Integer, primary_key=True, index=True)
    tema        = Column(String(200), nullable=False)  # ej: "Pricing pimple patches"
    duda        = Column(Text)                          # la pregunta que tenían
    conclusion  = Column(Text)                          # a qué llegaron
    contexto    = Column(JSON)                          # datos de respaldo (números, etc.)
    tags        = Column(String(500))                   # etiquetas separadas por coma
    created_at  = Column(DateTime, default=datetime.utcnow)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def init_db():
    """Crea todas las tablas si no existen."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency de FastAPI para obtener una sesión de DB."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
