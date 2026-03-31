"""
main.py — FastAPI application entry point.

Run with:
    uvicorn src.api.main:app --reload --port 8000

Interactive API docs available at:
    http://localhost:8000/docs     (Swagger UI)
    http://localhost:8000/redoc   (ReDoc)
"""

import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routes_search import router as search_router
from src.api.routes_templates import (
    templates_router,
    ingest_router,
    facets_router,
)
from src.api.routes_diff import diff_router, generate_router
from src.api.dependencies import get_pipeline, get_search_engine, _initialise
from src.api.models import HealthResponse
from src.config import EMBEDDING_BACKEND, VECTOR_STORE_BACKEND


# ─── Lifespan (startup / shutdown) ───────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks before the server accepts requests."""
    print("\n" + "="*60)
    print("  Trade Confirmation API — Starting Up")
    print("="*60)
    _initialise()
    engine = get_search_engine()
    count = engine._store.count()
    print(f"  ✅ Ready — {count} templates in store\n")
    yield
    print("\n  Trade Confirmation API — Shutting Down")


# ─── App ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Trade Confirmation Template API",
    description="""
## AI/ML-Driven Trade Confirmation Automation — Iterations 1 · 2 · 3

### Iteration 1 — Template Reuse
Semantic search over a centralised repository of trade confirmation templates.

### Iteration 2 — Difference Highlighting
Field-by-field comparison of two documents with risk scoring (HIGH / MEDIUM / LOW).

### Iteration 3 — Template Generator
Three-stage pipeline: auto-fill from trade data → AI clause suggestions → validation.
    """,
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ─── CORS ─────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Restrict to your domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request timing middleware ────────────────────────────────────────────

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    process_time = round((time.time() - start) * 1000, 2)
    response.headers["X-Process-Time-Ms"] = str(process_time)
    return response


# ─── Global exception handler ─────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": type(exc).__name__,
            "detail": str(exc),
            "status_code": 500,
        }
    )


# ─── Register routers ────────────────────────────────────────────────────

app.include_router(search_router)
app.include_router(templates_router)
app.include_router(ingest_router)
app.include_router(facets_router)
app.include_router(diff_router)
app.include_router(generate_router)


# ─── Root & Health ────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": "Trade Confirmation Template API",
        "docs": "/docs",
        "health": "/health",
        "version": "1.0.0",
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="API health check",
    description="Returns the current health status of the API and its components.",
)
async def health_check():
    engine = get_search_engine()
    pipeline = get_pipeline()
    count = engine._store.count()

    return HealthResponse(
        status="ok",
        version="1.0.0",
        templates_in_store=count,
        embedding_backend=pipeline.embedder.backend_name,
        vector_store_backend=VECTOR_STORE_BACKEND,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ─── Run directly ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["src"],
    )
