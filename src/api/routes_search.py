"""
routes_search.py — /search endpoint router.

Endpoints:
    POST /search          Search templates with a query + optional filters
    GET  /search/quick    Quick search via URL query params (for easy testing)
"""

import time
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from src.api.models import (
    SearchRequest,
    SearchResponse,
    TemplateResult,
    ErrorResponse,
)
from src.api.dependencies import get_search_engine

router = APIRouter(prefix="/search", tags=["Search"])


def _build_result(r) -> TemplateResult:
    """Convert a SearchResult into a TemplateResult response model."""
    meta = r.metadata
    return TemplateResult(
        doc_id=r.doc_id,
        filename=r.filename,
        score=r.score,
        trade_type=meta.get("trade_type", ""),
        counterparty=meta.get("counterparty", ""),
        jurisdiction=meta.get("jurisdiction", ""),
        product=meta.get("product", ""),
        version=meta.get("version", ""),
        status=meta.get("status", ""),
        title=meta.get("title", ""),
        snippet=r.snippet,
    )


@router.post(
    "",
    response_model=SearchResponse,
    summary="Semantic search for trade confirmation templates",
    description=(
        "Search the template repository using a natural language or keyword query. "
        "Optionally filter by trade_type, counterparty, jurisdiction, or product. "
        "Results are ranked by semantic similarity score (0–1)."
    ),
    responses={
        200: {"description": "Search completed successfully"},
        400: {"model": ErrorResponse, "description": "Invalid query"},
        500: {"model": ErrorResponse, "description": "Search engine error"},
    },
)
async def search_templates(
    request: SearchRequest,
    engine=Depends(get_search_engine),
):
    """
    ## Search Examples

    **Free text query:**
    ```json
    { "query": "Goldman Sachs interest rate swap USD SOFR" }
    ```

    **Query with filters:**
    ```json
    {
      "query": "floating rate quarterly",
      "trade_type": "Interest Rate Swap",
      "jurisdiction": "US",
      "top_k": 3
    }
    ```
    """
    start = time.time()

    # Build metadata filters from optional fields
    filters = {}
    if request.trade_type:
        filters["trade_type"] = request.trade_type
    if request.counterparty:
        filters["counterparty"] = request.counterparty
    if request.jurisdiction:
        filters["jurisdiction"] = request.jurisdiction
    if request.product:
        filters["product"] = request.product

    try:
        results = engine.search(
            query=request.query,
            top_k=request.top_k,
            filters=filters if filters else None,
            active_only=request.active_only,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    elapsed_ms = round((time.time() - start) * 1000, 2)

    return SearchResponse(
        query=request.query,
        filters_applied=filters,
        total_results=len(results),
        results=[_build_result(r) for r in results],
        search_time_ms=elapsed_ms,
    )


@router.get(
    "/quick",
    response_model=SearchResponse,
    summary="Quick search via URL params",
    description="Convenience GET endpoint for quick testing without a request body.",
)
async def quick_search(
    q: str = Query(..., min_length=2, description="Search query"),
    top_k: int = Query(default=5, ge=1, le=20),
    trade_type: Optional[str] = Query(default=None),
    jurisdiction: Optional[str] = Query(default=None),
    engine=Depends(get_search_engine),
):
    """
    Quick search via URL parameters.

    Example: `GET /search/quick?q=Goldman+Sachs+IRS&trade_type=Interest+Rate+Swap`
    """
    start = time.time()

    filters = {}
    if trade_type:
        filters["trade_type"] = trade_type
    if jurisdiction:
        filters["jurisdiction"] = jurisdiction

    try:
        results = engine.search(
            query=q,
            top_k=top_k,
            filters=filters if filters else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    elapsed_ms = round((time.time() - start) * 1000, 2)

    return SearchResponse(
        query=q,
        filters_applied=filters,
        total_results=len(results),
        results=[_build_result(r) for r in results],
        search_time_ms=elapsed_ms,
    )
