"""
MVP AI Agent Platform — FastAPI Application Entrypoint.

Self-hosted Supabase + Multi-Provider LLM Gateway.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import close_pool, create_pool

# ── Logging ──────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
log_format = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/app_{datetime.now().strftime('%Y%m%d')}.log"),
    ],
)
logger = logging.getLogger("app")


# ── Lifespan ─────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle hooks."""
    settings = get_settings()
    logger.info(f"Starting AI Agent Platform (env={settings.environment})")

    # Initialize database pool
    await create_pool()
    logger.info("Database pool ready")

    yield

    # Shutdown
    await close_pool()
    logger.info("Shutdown complete")


# ── App ──────────────────────────────────────────────────────
app = FastAPI(
    title="AI Agent Platform",
    description="MVP AI agent platform with multi-provider LLM support",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Session-ID"],
)

# ── Register Routes ──────────────────────────────────────────
from app.routes.auth import router as auth_router
from app.routes.api_keys import router as keys_router
from app.routes.sessions import router as sessions_router
from app.routes.chat import router as chat_router
from app.routes.agents import router as agents_router
from app.routes.providers import router as providers_router

app.include_router(auth_router)
app.include_router(keys_router)
app.include_router(sessions_router)
app.include_router(chat_router)
app.include_router(agents_router)
app.include_router(providers_router)


# ── Static Files (Frontend) ─────────────────────────────────
# Serve the frontend SPA
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


# ── Health Check ─────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "ai-agent-platform", "version": "0.1.0"}


# ── Root → Serve Frontend ───────────────────────────────────
@app.get("/")
async def root():
    """Serve the frontend SPA."""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            content = f.read()
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=content)
    return JSONResponse({"message": "AI Agent Platform API", "docs": "/docs"})


# ── Entrypoint ───────────────────────────────────────────────
if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=not settings.is_production,
        log_level=settings.log_level,
    )
