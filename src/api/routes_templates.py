"""
routes_templates.py — /templates and /ingest endpoint routers.

Endpoints:
    GET    /templates              List all templates in the repository
    GET    /templates/{doc_id}     Get full detail of a single template
    DELETE /templates/{doc_id}     Remove a template from the store
    POST   /ingest/file            Upload and ingest a new .docx template
    POST   /ingest/refresh         Re-ingest all templates from disk
    GET    /facets                 Get unique filter values for UI dropdowns
"""

import io
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import Optional

from src.api.models import (
    TemplateListResponse,
    TemplateListItem,
    TemplateDetailResponse,
    IngestResponse,
    BulkIngestResponse,
    FacetsResponse,
    DeleteResponse,
)
from src.api.dependencies import get_search_engine, get_pipeline
from src.config import TEMPLATES_DIR


# ─── /templates router ────────────────────────────────────────────────────

templates_router = APIRouter(prefix="/templates", tags=["Templates"])


@templates_router.get(
    "",
    response_model=TemplateListResponse,
    summary="List all templates in the repository",
    description="Returns all stored templates with their metadata. Use active_only=false to include drafts and deprecated templates.",
)
async def list_templates(
    active_only: bool = False,
    trade_type: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    product: Optional[str] = None,
    engine=Depends(get_search_engine),
):
    all_docs = engine.get_all_templates(active_only=active_only)

    # Apply optional filters
    if trade_type:
        all_docs = [d for d in all_docs if d.get("trade_type", "").lower() == trade_type.lower()]
    if jurisdiction:
        all_docs = [d for d in all_docs if d.get("jurisdiction", "").lower() == jurisdiction.lower()]
    if product:
        all_docs = [d for d in all_docs if d.get("product", "").lower() == product.lower()]

    items = [
        TemplateListItem(
            doc_id=d.get("doc_id", ""),
            filename=d.get("filename", ""),
            trade_type=d.get("trade_type", ""),
            counterparty=d.get("counterparty", ""),
            jurisdiction=d.get("jurisdiction", ""),
            product=d.get("product", ""),
            version=d.get("version", ""),
            status=d.get("status", ""),
            title=d.get("title", ""),
        )
        for d in all_docs
    ]

    return TemplateListResponse(total=len(items), templates=items)


@templates_router.get(
    "/{doc_id}",
    response_model=TemplateDetailResponse,
    summary="Get full detail of a single template",
    description="Returns complete metadata and full text of a specific template by its doc_id.",
    responses={404: {"description": "Template not found"}},
)
async def get_template(
    doc_id: str,
    engine=Depends(get_search_engine),
):
    all_docs = engine.get_all_templates(active_only=False)
    match = next((d for d in all_docs if d.get("doc_id") == doc_id), None)

    if not match:
        raise HTTPException(
            status_code=404,
            detail=f"Template with doc_id='{doc_id}' not found."
        )

    # Try to re-parse the file for full text + economic terms
    filename = match.get("filename", "")
    file_path = TEMPLATES_DIR / filename

    economic_terms = {}
    full_text = ""
    confirmation_body = ""

    if file_path.exists():
        from src.document_parser import DocumentParser
        parser = DocumentParser()
        try:
            parsed = parser.parse(file_path)
            full_text = parsed.full_text
            economic_terms = parsed.economic_terms
            confirmation_body = parsed.confirmation_body
        except Exception:
            full_text = "(Could not re-parse file)"

    return TemplateDetailResponse(
        doc_id=doc_id,
        filename=filename,
        trade_type=match.get("trade_type", ""),
        counterparty=match.get("counterparty", ""),
        jurisdiction=match.get("jurisdiction", ""),
        product=match.get("product", ""),
        version=match.get("version", ""),
        status=match.get("status", ""),
        title=match.get("title", ""),
        full_text=full_text,
        economic_terms=economic_terms,
        confirmation_body=confirmation_body,
    )


@templates_router.delete(
    "/{doc_id}",
    response_model=DeleteResponse,
    summary="Remove a template from the store",
    description="Deletes a template's vector and metadata from the store. The original .docx file is preserved on disk.",
    responses={404: {"description": "Template not found"}},
)
async def delete_template(
    doc_id: str,
    engine=Depends(get_search_engine),
):
    # Find filename before deleting
    all_docs = engine.get_all_templates(active_only=False)
    match = next((d for d in all_docs if d.get("doc_id") == doc_id), None)

    if not match:
        raise HTTPException(
            status_code=404,
            detail=f"Template with doc_id='{doc_id}' not found."
        )

    filename = match.get("filename", "unknown")
    deleted = engine._store.delete(doc_id)

    return DeleteResponse(
        doc_id=doc_id,
        filename=filename,
        deleted=deleted,
        message=f"Template '{filename}' removed from store. Source file preserved on disk.",
    )


@templates_router.get(
    "/{doc_id}/download",
    summary="Download the original .docx file",
    description="Streams the original .docx template file for download.",
    responses={
        404: {"description": "Template file not found on disk"},
    },
)
async def download_template(
    doc_id: str,
    engine=Depends(get_search_engine),
):
    all_docs = engine.get_all_templates(active_only=False)
    match = next((d for d in all_docs if d.get("doc_id") == doc_id), None)

    if not match:
        raise HTTPException(status_code=404, detail=f"Template '{doc_id}' not found.")

    filename = match.get("filename", "")
    file_path = TEMPLATES_DIR / filename

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Source file '{filename}' not found on disk."
        )

    return FileResponse(
        path=str(file_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )


# ─── /ingest router ───────────────────────────────────────────────────────

ingest_router = APIRouter(prefix="/ingest", tags=["Ingestion"])


@ingest_router.post(
    "/file",
    response_model=IngestResponse,
    summary="Upload and ingest a new template",
    description=(
        "Upload a .docx file. The system will parse it, generate embeddings, "
        "and store it in the vector repository. "
        "Use force=true to re-ingest a file that already exists."
    ),
    responses={
        400: {"description": "Unsupported file type"},
        500: {"description": "Ingestion failed"},
    },
)
async def ingest_file(
    file: UploadFile = File(..., description="The .docx template file to upload"),
    force: bool = Form(default=False, description="Re-ingest even if already in store"),
    pipeline=Depends(get_pipeline),
):
    # Validate file type
    if not file.filename.endswith((".docx", ".pdf", ".txt")):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: '{file.filename}'. Accepted: .docx, .pdf, .txt"
        )

    # Save upload to templates directory
    dest_path = TEMPLATES_DIR / file.filename
    content = await file.read()

    with open(dest_path, "wb") as f:
        f.write(content)

    # Ingest the saved file
    record = pipeline.ingest_file(dest_path, force=force)

    if not record.success and not record.skipped:
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {record.error}"
        )

    return IngestResponse(
        filename=record.filename,
        doc_id=record.doc_id,
        success=record.success,
        skipped=record.skipped,
        message=(
            "Already in store. Use force=true to re-ingest."
            if record.skipped
            else f"Successfully ingested '{record.filename}'"
        ),
        trade_type=record.trade_type,
        counterparty=record.counterparty,
    )


@ingest_router.post(
    "/refresh",
    response_model=BulkIngestResponse,
    summary="Re-ingest all templates from the templates directory",
    description=(
        "Scans the templates directory and ingests any new files. "
        "Use force=true to re-embed and re-index all files from scratch."
    ),
)
async def refresh_all(
    force: bool = False,
    pipeline=Depends(get_pipeline),
):
    report = pipeline.run(force=force)

    return BulkIngestResponse(
        total_found=report.total_files,
        ingested=report.ingested,
        skipped=report.skipped,
        failed=report.failed,
        duration_seconds=round(report.duration_seconds, 3),
        details=[
            {
                "filename": r.filename,
                "doc_id": r.doc_id,
                "success": r.success,
                "skipped": r.skipped,
                "error": r.error,
            }
            for r in report.records
        ],
    )


# ─── /facets router ───────────────────────────────────────────────────────

facets_router = APIRouter(prefix="/facets", tags=["Facets"])


@facets_router.get(
    "",
    response_model=FacetsResponse,
    summary="Get available filter values",
    description="Returns all unique metadata values in the store. Used to populate filter dropdowns in the UI.",
)
async def get_facets(engine=Depends(get_search_engine)):
    facets = engine.get_facets()
    total = engine._store.count()

    return FacetsResponse(
        trade_types=facets.get("trade_types", []),
        counterparties=facets.get("counterparties", []),
        jurisdictions=facets.get("jurisdictions", []),
        products=facets.get("products", []),
        total_templates=total,
    )
