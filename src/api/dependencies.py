"""
dependencies.py — FastAPI dependency injection.

Provides shared, singleton instances of the pipeline and search engine
to all route handlers via FastAPI's Depends() system.

On startup, the pipeline automatically ingests any templates in TEMPLATES_DIR
that haven't been ingested yet.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.ingestion_pipeline import IngestionPipeline
from src.search_engine import SearchEngine
from src.template_generator import generate_all_templates
from src.config import TEMPLATES_DIR, EMBEDDING_BACKEND, VECTOR_STORE_BACKEND

# ─── Singletons (created once at startup) ────────────────────────────────

_pipeline: IngestionPipeline | None = None
_search_engine: SearchEngine | None = None


def _initialise():
    """
    Lazily initialise the pipeline and search engine on first request.
    In production, call this explicitly in the FastAPI lifespan hook.
    """
    global _pipeline, _search_engine

    if _pipeline is None:
        # Generate sample templates if templates dir is empty
        existing = list(TEMPLATES_DIR.glob("*.docx"))
        if not existing:
            print("\n  [startup] No templates found — generating samples...")
            generate_all_templates()

        # Build pipeline
        _pipeline = IngestionPipeline(
            embedding_backend=EMBEDDING_BACKEND,
            vector_store_backend=VECTOR_STORE_BACKEND,
        )

        # Ingest any templates not yet in the store
        _pipeline.run(force=False)

    if _search_engine is None:
        _search_engine = SearchEngine.from_pipeline(_pipeline)


# ─── Dependency functions ─────────────────────────────────────────────────

def get_pipeline() -> IngestionPipeline:
    """FastAPI dependency: returns the shared IngestionPipeline instance."""
    _initialise()
    return _pipeline


def get_search_engine() -> SearchEngine:
    """FastAPI dependency: returns the shared SearchEngine instance."""
    _initialise()
    return _search_engine
