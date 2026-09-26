# -*- coding: utf-8 -*-
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers.v1 import inventory

app = FastAPI(
    title="TCG & Gacha Bot API",
    version="1.0.0",
    description="Backend para autenticación de Telegram Mini App e inventario TCG."
)

# 1. Configurar Middleware de CORS
# Permite solicitudes desde GitHub Pages y entorno de desarrollo local
origins = [
    "https://*.github.io",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "*"  # En producción puedes restringir al dominio exacto de tu GitHub Pages
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Registrar el router del inventario
app.include_router(inventory.router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
def health_check():
    """Verificación de estado del servidor."""
    return {"status": "ok", "service": "FastAPI TCG Engine"}
