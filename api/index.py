"""
api/index.py — Punto de entrada para Vercel (serverless)
Importa la app FastAPI desde backend/main.py
"""
import sys
import os

# Agrega backend/ al path para que los imports funcionen
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from main import app  # noqa: F401 — Vercel busca la variable 'app'
