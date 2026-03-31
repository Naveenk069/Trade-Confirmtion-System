"""
models.py — Pydantic request/response schemas for the Trade Confirmation API.

Every API input and output is strictly typed here.
FastAPI uses these to:
  - Validate incoming requests automatically
  - Generate the Swagger /docs UI
  - Serialize responses to JSON
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


# ─── Shared / Enums ───────────────────────────────────────────────────────

VALID_TRADE_TYPES = [
    "Interest Rate Swap",
    "FX Forward",
    "Credit Default Swap",
    "Equity Swap",
    "Total Return Swap",
    "Cross Currency Swap",
]

VALID_JURISDICTIONS = ["US", "UK", "EU", "APAC", "OTHER"]
VALID_STATUSES      = ["active", "draft", "deprecated"]
VALID_PRODUCTS      = ["IRS", "FX", "CDS", "Equity Swap", "TRS", "XCS"]


# ─── /health ──────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = Field(..., example="ok")
    version: str = Field(..., example="1.0.0")
    templates_in_store: int = Field(..., example=8)
    embedding_backend: str = Field(..., example="TF-IDF (numpy)")
    vector_store_backend: str = Field(..., example="json")
    timestamp: str


# ─── /search ──────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    """Body for POST /search"""
    query: str = Field(
        ...,
        min_length=2,
        max_length=500,
        example="Goldman Sachs interest rate swap USD SOFR 5 year",
        description="Natural language or keyword search query"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of results to return (1–20)"
    )
    trade_type: Optional[str] = Field(
        default=None,
        example="Interest Rate Swap",
        description="Filter by trade type"
    )
    counterparty: Optional[str] = Field(
        default=None,
        example="Goldman Sachs",
        description="Filter by counterparty name"
    )
    jurisdiction: Optional[str] = Field(
        default=None,
        example="US",
        description="Filter by jurisdiction (US / UK / EU)"
    )
    product: Optional[str] = Field(
        default=None,
        example="IRS",
        description="Filter by product code"
    )
    active_only: bool = Field(
        default=True,
        description="If true, only return templates with status=active"
    )

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, v):
        if not v.strip():
            raise ValueError("Query cannot be blank or whitespace only.")
        return v.strip()


class TemplateResult(BaseModel):
    """A single search result."""
    doc_id: str
    filename: str
    score: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score")
    trade_type: str
    counterparty: str
    jurisdiction: str
    product: str
    version: str
    status: str
    title: str
    snippet: str = Field(..., description="First 300 characters of template text")


class SearchResponse(BaseModel):
    query: str
    filters_applied: dict
    total_results: int
    results: list[TemplateResult]
    search_time_ms: float


# ─── /templates ───────────────────────────────────────────────────────────

class TemplateListItem(BaseModel):
    """One row in the template browser list."""
    doc_id: str
    filename: str
    trade_type: str
    counterparty: str
    jurisdiction: str
    product: str
    version: str
    status: str
    title: str


class TemplateListResponse(BaseModel):
    total: int
    templates: list[TemplateListItem]


class TemplateDetailResponse(BaseModel):
    """Full detail for a single template."""
    doc_id: str
    filename: str
    trade_type: str
    counterparty: str
    jurisdiction: str
    product: str
    version: str
    status: str
    title: str
    full_text: str
    economic_terms: dict
    confirmation_body: str


# ─── /ingest ──────────────────────────────────────────────────────────────

class IngestResponse(BaseModel):
    """Response after uploading a new template."""
    filename: str
    doc_id: str
    success: bool
    skipped: bool = False
    message: str
    trade_type: str = ""
    counterparty: str = ""


class BulkIngestResponse(BaseModel):
    """Response after bulk re-ingestion."""
    total_found: int
    ingested: int
    skipped: int
    failed: int
    duration_seconds: float
    details: list[dict]


# ─── /facets ──────────────────────────────────────────────────────────────

class FacetsResponse(BaseModel):
    """Available filter values for the UI dropdowns."""
    trade_types: list[str]
    counterparties: list[str]
    jurisdictions: list[str]
    products: list[str]
    total_templates: int


# ─── /templates/{id} DELETE ───────────────────────────────────────────────

class DeleteResponse(BaseModel):
    doc_id: str
    filename: str
    deleted: bool
    message: str


# ─── Error responses ──────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: str
    detail: str
    status_code: int
