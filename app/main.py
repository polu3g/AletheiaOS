from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import v1_router
from app.config import get_settings
from app.db import create_tables, get_db
from app.models.api_models import HealthResponse, MemoryStats, StatusResponse

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("aletheia")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AletheiaOS %s starting up…", settings.app_version)
    create_tables()
    logger.info("Database tables ready")
    yield
    logger.info("AletheiaOS shutting down")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.app_description,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "AletheiaOS Project",
        "url": "https://github.com/yourusername/AletheiaOS",
    },
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next) -> Response:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    t0 = time.perf_counter()
    response = await call_next(request)
    elapsed = round((time.perf_counter() - t0) * 1000, 1)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = str(elapsed)
    return response


# ── Exception handlers ────────────────────────────────────────────────────────

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    logger.exception("Runtime error on %s", request.url)
    return JSONResponse(status_code=500, content={"detail": str(exc)})


# ── System endpoints ──────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check",
    description="Lightweight liveness probe — returns 200 when the service is up.",
)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.app_version)


@app.get(
    "/api/v1/status",
    response_model=StatusResponse,
    tags=["System"],
    summary="Detailed system status",
    description="Returns database connectivity, memory counts, and world model size.",
)
def status() -> StatusResponse:
    db_gen = get_db()
    db = next(db_gen)
    try:
        from app.logging.trace import TraceService
        from app.memory.episodic import EpisodicMemoryService
        from app.memory.semantic import SemanticMemoryService
        from app.world_model.state import WorldModelService

        mem = MemoryStats(
            episodic_count=EpisodicMemoryService(db).count(),
            semantic_count=SemanticMemoryService(db).count(),
            trace_count=TraceService(db).count(),
        )
        world_count = WorldModelService(db).entry_count()
        db_status = "connected"
    except Exception as exc:
        logger.error("Status check DB error: %s", exc)
        mem = MemoryStats(episodic_count=0, semantic_count=0, trace_count=0)
        world_count = 0
        db_status = f"error: {exc}"
    finally:
        try:
            db_gen.close()
        except Exception:
            pass

    return StatusResponse(
        status="ok",
        version=settings.app_version,
        database=db_status,
        memory=mem,
        world_model_entries=world_count,
    )


# ── API routes ────────────────────────────────────────────────────────────────

app.include_router(v1_router)
