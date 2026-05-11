"""
Backend del Agente de Productos — OpheraBeauty E-Commerce UY
FastAPI + Claude API (Anthropic) + SQLite (SQLAlchemy)
"""

import os
import json
import re
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import anthropic
import httpx
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from database import (
    init_db, get_db,
    Product, ProductSearch, Campaign, CampaignMetrics, BusinessNote, SourcingItem
)

load_dotenv()

app = FastAPI(title="OpheraBeauty — Agente E-Commerce UY", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


@app.on_event("startup")
def startup():
    init_db()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class BuscarProductosRequest(BaseModel):
    categoria: Optional[str] = ""
    margen_minimo: Optional[float] = 5.0
    cantidad: Optional[int] = 5


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class ProductCreate(BaseModel):
    nombre: str
    categoria: Optional[str] = None
    url_alibaba: Optional[str] = None
    url_aliexpress: Optional[str] = None
    costo_usd: Optional[float] = None
    precio_venta_uyu: Optional[float] = None
    stock: Optional[int] = 0
    estado: Optional[str] = "en_analisis"
    notas: Optional[str] = None


class ProductUpdate(BaseModel):
    nombre: Optional[str] = None
    categoria: Optional[str] = None
    url_alibaba: Optional[str] = None
    url_aliexpress: Optional[str] = None
    costo_usd: Optional[float] = None
    precio_venta_uyu: Optional[float] = None
    stock: Optional[int] = None
    estado: Optional[str] = None
    notas: Optional[str] = None


class CampaignCreate(BaseModel):
    nombre: str
    product_id: Optional[int] = None
    objetivo: Optional[str] = "TRAFFIC"
    presupuesto_diario_usd: Optional[float] = None
    audiencia_descripcion: Optional[str] = None
    copy_headline: Optional[str] = None
    copy_texto: Optional[str] = None
    copy_cta: Optional[str] = None
    notas: Optional[str] = None


class CampaignMetricsCreate(BaseModel):
    campaign_id: int
    fecha: str
    impresiones: Optional[int] = 0
    clicks: Optional[int] = 0
    ctr: Optional[float] = 0.0
    cpc: Optional[float] = 0.0
    gasto_usd: Optional[float] = 0.0
    alcance: Optional[int] = 0
    ventas: Optional[int] = 0
    roas: Optional[float] = 0.0


class BusinessNoteCreate(BaseModel):
    tema: str
    duda: Optional[str] = None
    conclusion: Optional[str] = None
    contexto: Optional[dict] = None
    tags: Optional[str] = None


class SourcingItemCreate(BaseModel):
    producto: str
    marca: Optional[str] = None
    presentacion: Optional[str] = None
    categoria: Optional[str] = None
    pais_origen: str
    bandera: Optional[str] = None
    moneda: Optional[str] = "USD"
    precio_origen: Optional[float] = None
    tipo_cambio_uyu: Optional[float] = None
    peso_kg: Optional[float] = None
    fuente: Optional[str] = None
    costo_envio_uyu: Optional[float] = 0
    precio_mercado_uy: Optional[float] = None
    precio_venta_sugerido: Optional[float] = None
    notas: Optional[str] = None


class SourcingItemUpdate(BaseModel):
    producto: Optional[str] = None
    marca: Optional[str] = None
    presentacion: Optional[str] = None
    categoria: Optional[str] = None
    pais_origen: Optional[str] = None
    bandera: Optional[str] = None
    moneda: Optional[str] = None
    precio_origen: Optional[float] = None
    tipo_cambio_uyu: Optional[float] = None
    peso_kg: Optional[float] = None
    fuente: Optional[str] = None
    costo_envio_uyu: Optional[float] = None
    precio_mercado_uy: Optional[float] = None
    precio_venta_sugerido: Optional[float] = None
    notas: Optional[str] = None


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT_AGENTE = """
Sos el Agente OpheraBeauty: CEO y consultor estratégico de un emprendimiento de e-commerce en Uruguay.
Tu rol combina dos perspectivas:

1. **CEO**: Tomás decisiones con visión de largo plazo. Priorizás rentabilidad, escalabilidad y foco.
   Sabés qué hacer primero y qué descartar. Sos directo y no te perdés en detalles innecesarios.

2. **Consultor**: Analizás problemas con profundidad. Hacés preguntas clave, identificás riesgos,
   y das recomendaciones concretas basadas en el contexto del negocio.

Contexto del negocio:
- Marca: OpheraBeauty — e-commerce orientado a Uruguay
- Primera línea: pimple patches y productos de higiene femenina
- Canales: Instagram, TikTok, WhatsApp
- Proveedores: AliExpress, Alibaba
- Logística: DAC (envíos locales Uruguay)
- Moneda: pesos uruguayos (UYU) y dólares (USD)

Cómo respondés:
- Directo, sin rodeos, con lenguaje rioplatense uruguayo natural
- Cuando alguien tiene una duda, la respondés con claridad y ejemplos concretos
- Si es una decisión estratégica, das tu opinión clara y justificada
- Usás markdown simple: **negrita**, listas con -, párrafos cortos
- No sos un asistente genérico: sos el CEO de este emprendimiento
""".strip()


def construir_prompt(categoria: str, margen_minimo: float, cantidad: int) -> str:
    categoria_texto = categoria if categoria else "cualquier categoría"
    return f"""
# ROL
Sos un experto en dropshipping, importación y comercio electrónico en Uruguay con 10 años de experiencia.
Conocés AliExpress, Alibaba y el mercado uruguayo en profundidad: demanda, Instagram, DAC, OCA.

# TAREA
Recomendá exactamente {cantidad} productos para vender online en Uruguay con alto margen y poca competencia.

# CONTEXTO
- Categoría: {categoria_texto}
- Margen mínimo: {margen_minimo}x
- Mercado: Uruguay (precios en UYU)
- Canal: Instagram, TikTok, WhatsApp
- Modelo: dropshipping o stock pequeño (3-10 unidades)
- Proveedor: AliExpress

# OUTPUT
Solo JSON válido, sin texto extra:

{{
  "productos": [
    {{
      "nombre": "Nombre en español",
      "categoria": "Categoría",
      "puntaje": 8,
      "costo_estimado_usd": 18,
      "precio_venta_sugerido_uyu": 890,
      "margen": 5.9,
      "termino_busqueda": "exact aliexpress search term in english",
      "termino_ml": "término mercadolibre uruguay",
      "analisis": "Análisis de demanda, competencia y viabilidad en Uruguay.",
      "speech": "Copy para Instagram/WhatsApp en español rioplatense con emojis.",
      "riesgo": "Bajo",
      "riesgo_detalle": "Riesgos y cómo mitigarlos."
    }}
  ]
}}
""".strip()


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/")
def health_check():
    return {"status": "ok", "agente": "OpheraBeauty v2.0"}


# ── Chat ──────────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(request: ChatRequest):
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY no configurada.")
    if not request.messages:
        raise HTTPException(status_code=400, detail="Se requiere al menos un mensaje.")

    messages = [
        {"role": m.role, "content": m.content}
        for m in request.messages
        if m.role in ("user", "assistant")
    ]

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT_AGENTE,
            messages=messages,
        )
        return {"response": msg.content[0].text.strip()}
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="API key inválida.")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Límite de requests alcanzado.")
    except anthropic.APIError as e:
        raise HTTPException(status_code=500, detail=f"Error API: {str(e)}")


# ── Buscar productos (agente) ─────────────────────────────────────────────────

@app.post("/api/agent/buscar-productos")
async def buscar_productos(request: BuscarProductosRequest, db: Session = Depends(get_db)):
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY no configurada.")

    prompt = construir_prompt(
        categoria=request.categoria or "",
        margen_minimo=request.margen_minimo or 5.0,
        cantidad=request.cantidad or 5,
    )

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        texto = msg.content[0].text.strip()
        texto = re.sub(r"^```(?:json)?\s*", "", texto)
        texto = re.sub(r"\s*```$", "", texto)

        try:
            data = json.loads(texto)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail=f"JSON inválido: {texto[:300]}")

        if "productos" not in data:
            raise HTTPException(status_code=500, detail="Falta el campo 'productos'.")

        # Auto-guardar búsqueda en DB
        try:
            record = ProductSearch(
                categoria=request.categoria or "general",
                margen_minimo=request.margen_minimo,
                cantidad=request.cantidad,
                resultado_json=data["productos"],
                total_resultados=len(data["productos"]),
            )
            db.add(record)
            db.commit()
        except Exception:
            db.rollback()

        return data

    except anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="API key inválida.")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Límite de requests alcanzado.")
    except anthropic.APIError as e:
        raise HTTPException(status_code=500, detail=f"Error Anthropic: {str(e)}")


# ── MercadoLibre proxy ────────────────────────────────────────────────────────

@app.get("/api/ml/precios")
async def ml_precios(q: str = Query(..., description="Término de búsqueda para MercadoLibre UY")):
    url = "https://api.mercadolibre.com/sites/MLU/search"
    params = {"q": q, "sort": "price_asc", "limit": 20}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Accept-Language": "es-UY,es;q=0.9",
        "Referer": "https://www.mercadolibre.com.uy/",
        "Origin": "https://www.mercadolibre.com.uy",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])
        filtrados = [it for it in results if it.get("sold_quantity", 0) >= 3]
        if len(filtrados) < 2:
            filtrados = results[:10]
        if not filtrados:
            return {"total": 0, "items": []}

        precios = [it["price"] for it in filtrados]
        top3 = [
            {
                "titulo": it["title"],
                "precio": it["price"],
                "vendidos": it.get("sold_quantity", 0),
                "link": it.get("permalink", ""),
                "thumbnail": it.get("thumbnail", ""),
            }
            for it in filtrados[:3]
        ]

        return {
            "total": data.get("paging", {}).get("total", len(results)),
            "min_precio": min(precios),
            "max_precio": max(precios),
            "avg_precio": round(sum(precios) / len(precios)),
            "items": top3,
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"ML error {e.response.status_code}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=502, detail="MercadoLibre timeout")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error ML: {str(e)}")


# ── Productos CRUD ────────────────────────────────────────────────────────────

@app.get("/api/products")
def listar_productos(estado: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Product)
    if estado:
        q = q.filter(Product.estado == estado)
    return [_product_to_dict(p) for p in q.order_by(Product.created_at.desc()).all()]


@app.post("/api/products", status_code=201)
def crear_producto(data: ProductCreate, db: Session = Depends(get_db)):
    margen = None
    if data.costo_usd and data.precio_venta_uyu:
        costo_uyu = data.costo_usd * 43
        margen = round(data.precio_venta_uyu / costo_uyu, 2) if costo_uyu > 0 else None

    producto = Product(
        nombre=data.nombre,
        categoria=data.categoria,
        url_alibaba=data.url_alibaba,
        url_aliexpress=data.url_aliexpress,
        costo_usd=data.costo_usd,
        precio_venta_uyu=data.precio_venta_uyu,
        margen=margen,
        stock=data.stock or 0,
        estado=data.estado or "en_analisis",
        notas=data.notas,
    )
    db.add(producto)
    db.commit()
    db.refresh(producto)
    return _product_to_dict(producto)


@app.get("/api/products/{product_id}")
def obtener_producto(product_id: int, db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return _product_to_dict(p)


@app.patch("/api/products/{product_id}")
def actualizar_producto(product_id: int, data: ProductUpdate, db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(p, field, value)

    if p.costo_usd and p.precio_venta_uyu:
        costo_uyu = p.costo_usd * 43
        p.margen = round(p.precio_venta_uyu / costo_uyu, 2) if costo_uyu > 0 else None

    p.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(p)
    return _product_to_dict(p)


@app.post("/api/products/from-search/{search_id}/{producto_index}", status_code=201)
def guardar_producto_de_busqueda(
    search_id: int,
    producto_index: int,
    db: Session = Depends(get_db)
):
    search = db.query(ProductSearch).filter(ProductSearch.id == search_id).first()
    if not search:
        raise HTTPException(status_code=404, detail="Búsqueda no encontrada")

    productos = search.resultado_json
    if producto_index >= len(productos):
        raise HTTPException(status_code=404, detail="Índice fuera de rango")

    p = productos[producto_index]
    costo_usd = p.get("costo_estimado_usd") or p.get("costo_proveedor")
    precio_uyu = p.get("precio_venta_sugerido_uyu") or p.get("precio_venta_sugerido")

    producto = Product(
        nombre=p.get("nombre", "Sin nombre"),
        categoria=p.get("categoria"),
        costo_usd=costo_usd,
        precio_venta_uyu=precio_uyu,
        margen=p.get("margen"),
        estado="en_analisis",
        puntaje=p.get("puntaje"),
        speech=p.get("speech"),
        analisis=p.get("analisis"),
        riesgo=p.get("riesgo"),
        termino_busqueda=p.get("termino_busqueda"),
        termino_ml=p.get("termino_ml"),
    )
    db.add(producto)
    db.commit()
    db.refresh(producto)
    return _product_to_dict(producto)


# ── Historial de búsquedas ────────────────────────────────────────────────────

@app.get("/api/searches")
def listar_busquedas(limit: int = 20, db: Session = Depends(get_db)):
    searches = db.query(ProductSearch).order_by(ProductSearch.created_at.desc()).limit(limit).all()
    return [
        {
            "id": s.id,
            "categoria": s.categoria,
            "margen_minimo": s.margen_minimo,
            "cantidad": s.cantidad,
            "total_resultados": s.total_resultados,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in searches
    ]


@app.get("/api/searches/{search_id}")
def obtener_busqueda(search_id: int, db: Session = Depends(get_db)):
    s = db.query(ProductSearch).filter(ProductSearch.id == search_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Búsqueda no encontrada")
    return {
        "id": s.id,
        "categoria": s.categoria,
        "margen_minimo": s.margen_minimo,
        "cantidad": s.cantidad,
        "total_resultados": s.total_resultados,
        "productos": s.resultado_json,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


# ── Campañas CRUD ─────────────────────────────────────────────────────────────

@app.get("/api/campaigns")
def listar_campanas(db: Session = Depends(get_db)):
    return [_campaign_to_dict(c) for c in db.query(Campaign).order_by(Campaign.created_at.desc()).all()]


@app.post("/api/campaigns", status_code=201)
def crear_campana(data: CampaignCreate, db: Session = Depends(get_db)):
    c = Campaign(
        nombre=data.nombre,
        product_id=data.product_id,
        objetivo=data.objetivo,
        presupuesto_diario_usd=data.presupuesto_diario_usd,
        audiencia_descripcion=data.audiencia_descripcion,
        copy_headline=data.copy_headline,
        copy_texto=data.copy_texto,
        copy_cta=data.copy_cta,
        notas=data.notas,
        estado="borrador",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _campaign_to_dict(c)


@app.patch("/api/campaigns/{campaign_id}")
def actualizar_campana(campaign_id: int, data: dict, db: Session = Depends(get_db)):
    c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    for field, value in data.items():
        if hasattr(c, field):
            setattr(c, field, value)
    c.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(c)
    return _campaign_to_dict(c)


# ── Métricas de campaña ───────────────────────────────────────────────────────

@app.get("/api/campaigns/{campaign_id}/metrics")
def obtener_metricas(campaign_id: int, db: Session = Depends(get_db)):
    metrics = (
        db.query(CampaignMetrics)
        .filter(CampaignMetrics.campaign_id == campaign_id)
        .order_by(CampaignMetrics.fecha.asc())
        .all()
    )
    return [_metrics_to_dict(m) for m in metrics]


@app.post("/api/campaigns/{campaign_id}/metrics", status_code=201)
def agregar_metricas(campaign_id: int, data: CampaignMetricsCreate, db: Session = Depends(get_db)):
    if not db.query(Campaign).filter(Campaign.id == campaign_id).first():
        raise HTTPException(status_code=404, detail="Campaña no encontrada")

    m = CampaignMetrics(
        campaign_id=campaign_id,
        fecha=datetime.fromisoformat(data.fecha),
        impresiones=data.impresiones,
        clicks=data.clicks,
        ctr=data.ctr,
        cpc=data.cpc,
        gasto_usd=data.gasto_usd,
        alcance=data.alcance,
        ventas=data.ventas,
        roas=data.roas,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return {"id": m.id, "campaign_id": m.campaign_id, "fecha": data.fecha}


# ── Notas de negocio ──────────────────────────────────────────────────────────

@app.get("/api/notes")
def listar_notas(tag: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(BusinessNote)
    if tag:
        q = q.filter(BusinessNote.tags.contains(tag))
    return [_note_to_dict(n) for n in q.order_by(BusinessNote.created_at.desc()).all()]


@app.post("/api/notes", status_code=201)
def crear_nota(data: BusinessNoteCreate, db: Session = Depends(get_db)):
    n = BusinessNote(
        tema=data.tema,
        duda=data.duda,
        conclusion=data.conclusion,
        contexto=data.contexto,
        tags=data.tags,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return _note_to_dict(n)


@app.delete("/api/notes/{note_id}", status_code=204)
def eliminar_nota(note_id: int, db: Session = Depends(get_db)):
    n = db.query(BusinessNote).filter(BusinessNote.id == note_id).first()
    if not n:
        raise HTTPException(status_code=404, detail="Nota no encontrada")
    db.delete(n)
    db.commit()

# ── Serialización ─────────────────────────────────────────────────────────────

def _product_to_dict(p):
    return {
        "id": p.id, "nombre": p.nombre, "categoria": p.categoria,
        "url_alibaba": p.url_alibaba, "url_aliexpress": p.url_aliexpress,
        "costo_usd": p.costo_usd, "precio_venta_uyu": p.precio_venta_uyu,
        "margen": p.margen, "stock": p.stock, "estado": p.estado,
        "puntaje": p.puntaje, "speech": p.speech, "analisis": p.analisis,
        "riesgo": p.riesgo, "notas": p.notas,
        "termino_busqueda": p.termino_busqueda, "termino_ml": p.termino_ml,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }

def _campaign_to_dict(c):
    return {
        "id": c.id, "nombre": c.nombre, "product_id": c.product_id,
        "objetivo": c.objetivo, "presupuesto_diario_usd": c.presupuesto_diario_usd,
        "audiencia_descripcion": c.audiencia_descripcion,
        "copy_headline": c.copy_headline, "copy_texto": c.copy_texto,
        "copy_cta": c.copy_cta, "estado": c.estado,
        "meta_campaign_id": c.meta_campaign_id, "meta_adset_id": c.meta_adset_id,
        "meta_ad_id": c.meta_ad_id, "notas": c.notas,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }

def _metrics_to_dict(m):
    return {
        "id": m.id, "campaign_id": m.campaign_id,
        "fecha": m.fecha.isoformat() if m.fecha else None,
        "impresiones": m.impresiones, "clicks": m.clicks, "ctr": m.ctr,
        "cpc": m.cpc, "gasto_usd": m.gasto_usd, "alcance": m.alcance,
        "ventas": m.ventas, "roas": m.roas,
    }

def _note_to_dict(n):
    return {
        "id": n.id, "tema": n.tema, "duda": n.duda, "conclusion": n.conclusion,
        "contexto": n.contexto, "tags": n.tags,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }

def _sourcing_to_dict(s):
    costo_origen_uyu = (s.precio_origen or 0) * (s.tipo_cambio_uyu or 1)
    costo_total_uyu  = costo_origen_uyu + (s.costo_envio_uyu or 0)
    pvp = s.precio_venta_sugerido or 0
    margen_pct = round((pvp - costo_total_uyu) / pvp * 100, 1) if pvp > 0 else None
    return {
        "id": s.id,
        "producto": s.producto,
        "marca": s.marca,
        "presentacion": s.presentacion,
        "categoria": s.categoria,
        "pais_origen": s.pais_origen,
        "bandera": s.bandera,
        "moneda": s.moneda,
        "precio_origen": s.precio_origen,
        "tipo_cambio_uyu": s.tipo_cambio_uyu,
        "peso_kg": s.peso_kg,
        "fuente": s.fuente,
        "costo_envio_uyu": s.costo_envio_uyu,
        "precio_mercado_uy": s.precio_mercado_uy,
        "precio_venta_sugerido": s.precio_venta_sugerido,
        "notas": s.notas,
        # campos calculados
        "costo_origen_uyu": round(costo_origen_uyu, 2),
        "costo_total_uyu": round(costo_total_uyu, 2),
        "margen_pct": margen_pct,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


# ── Sourcing Lab ──────────────────────────────────────────────────────────────

@app.get("/api/sourcing")
def listar_sourcing(categoria: Optional[str] = None, pais: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(SourcingItem)
    if categoria:
        q = q.filter(SourcingItem.categoria == categoria)
    if pais:
        q = q.filter(SourcingItem.pais_origen == pais)
    items = q.order_by(SourcingItem.producto.asc(), SourcingItem.pais_origen.asc()).all()
    return [_sourcing_to_dict(s) for s in items]


@app.post("/api/sourcing", status_code=201)
def crear_sourcing(data: SourcingItemCreate, db: Session = Depends(get_db)):
    s = SourcingItem(
        producto=data.producto,
        marca=data.marca,
        presentacion=data.presentacion,
        categoria=data.categoria,
        pais_origen=data.pais_origen,
        bandera=data.bandera,
        moneda=data.moneda or "USD",
        precio_origen=data.precio_origen,
        tipo_cambio_uyu=data.tipo_cambio_uyu,
        peso_kg=data.peso_kg,
        fuente=data.fuente,
        costo_envio_uyu=data.costo_envio_uyu or 0,
        precio_mercado_uy=data.precio_mercado_uy,
        precio_venta_sugerido=data.precio_venta_sugerido,
        notas=data.notas,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _sourcing_to_dict(s)


@app.patch("/api/sourcing/{item_id}")
def actualizar_sourcing(item_id: int, data: SourcingItemUpdate, db: Session = Depends(get_db)):
    s = db.query(SourcingItem).filter(SourcingItem.id == item_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Ítem de sourcing no encontrado")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(s, field, value)
    s.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(s)
    return _sourcing_to_dict(s)


@app.delete("/api/sourcing/{item_id}", status_code=204)
def eliminar_sourcing(item_id: int, db: Session = Depends(get_db)):
    s = db.query(SourcingItem).filter(SourcingItem.id == item_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Ítem de sourcing no encontrado")
    db.delete(s)
    db.commit()
