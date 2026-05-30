"""
Smart Traffic Monitoring System (STMS) — FastAPI Application Main Module

Entry point untuk STMS backend application. Menginisialisasi:
- FastAPI app
- CORS middleware
- Database connection
- Background scheduler untuk kalkulasi density
- API routers untuk authentication, cameras, detections, density, alerts, reports, stream
- Global exception handlers (format error standar)

All configuration is loaded from config.py which reads from .env file.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from apscheduler.schedulers.background import BackgroundScheduler

from . import config, database
from .routers import cameras, auth, detections, stream, density, alerts, reports
from .init_cameras import init_default_cameras
from .tasks import calculate_density_task

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING SETUP
# ═══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("stms")

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

try:
    config.validate_config()
    config.print_config_summary()
except ValueError as e:
    print(f"❌ Configuration Error: {e}")
    raise


# ═══════════════════════════════════════════════════════════════════════════════
# BACKGROUND SCHEDULER SETUP
# ═══════════════════════════════════════════════════════════════════════════════

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager untuk startup dan shutdown events.

    Startup: Initialize database, scheduler
    Shutdown: Stop scheduler
    """
    # ─────── STARTUP ───────
    # Initialize database (create tables)
    database.init_db()

    # Initialize default camera jika belum ada
    init_default_cameras()

    # Start background scheduler untuk kalkulasi density
    if not scheduler.running:
        scheduler.add_job(
            calculate_density_task,
            'interval',
            minutes=config.DENSITY_INTERVAL_MINUTES,
            id='calculate_density_job'
        )
        scheduler.start()
        logger.info(
            f"✅ Background scheduler started (interval: {config.DENSITY_INTERVAL_MINUTES} minutes)"
        )

    yield

    # ─────── SHUTDOWN ───────
    if scheduler.running:
        scheduler.shutdown()
        logger.info("✅ Background scheduler stopped")


# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Smart Traffic Monitoring System (STMS) API",
    description=(
        "Backend API untuk analisis tren lalu lintas di area wisata "
        "dengan YOLOv8 & PostgreSQL — Capstone President University"
    ),
    version="1.0.0",
    lifespan=lifespan,
    # Custom error responses mengikuti format standar {"error": true, "code": "...", "message": "..."}
    responses={
        400: {"description": "Bad Request"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"},
    }
)


# ═══════════════════════════════════════════════════════════════════════════════
# MIDDLEWARE SETUP
# ═══════════════════════════════════════════════════════════════════════════════

# CORS middleware — baca allowed origins dari config.py (sudah berupa list)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"✅ CORS enabled for origins: {', '.join(config.ALLOWED_ORIGINS)}")


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL EXCEPTION HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all handler untuk unhandled exception — format error standar."""
    logger.error(f"Unhandled exception on {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "code": "INTERNAL_ERROR",
            "message": "Terjadi kesalahan internal server."
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handler untuk Pydantic/FastAPI validation error — format error standar."""
    return JSONResponse(
        status_code=400,
        content={
            "error": True,
            "code": "VALIDATION_ERROR",
            "message": str(exc.errors())
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# API ROUTERS REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════════

# Existing routers
app.include_router(auth.router)         # /api/v1/auth/**
app.include_router(cameras.router)      # /api/v1/cameras/**
app.include_router(detections.router)   # /api/v1/detections/**
app.include_router(stream.router)       # /api/v1/stream/**

# New routers (Phase 4)
app.include_router(density.router, tags=["Density"])   # /api/v1/density/**
app.include_router(alerts.router, tags=["Alerts"])     # /api/v1/alerts/**
app.include_router(reports.router, tags=["Reports"])   # /api/v1/reports/**

logger.info("✅ All API routers registered")


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/", tags=["Health"])
def root() -> dict:
    """Root endpoint — health check cepat untuk load balancer / Docker healthcheck."""
    return {
        "status": "ok",
        "system": "STMS Backend",
        "version": "1.0.0"
    }


@app.get("/health", tags=["Health"])
def health_check() -> dict:
    """Health check endpoint yang juga menguji koneksi database."""
    try:
        with database.SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("Database health check failed", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Database unavailable or not reachable"
        )

    return {
        "status": "healthy",
        "service": "STMS Backend",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )