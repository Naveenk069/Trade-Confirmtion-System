"""
routes_diff.py — API endpoints for Iteration 2 (Diff Engine) and Iteration 3 (Template Populator).

Endpoints:
  POST /diff/compare          — Compare two stored templates by doc_id
  POST /diff/compare-text     — Compare two raw text blocks
  POST /diff/compare-upload   — Upload two .docx files and compare them

  POST /generate              — Generate pre-populated template from trade data (JSON body)
  POST /generate/from-json    — Upload a JSON file and generate
  POST /generate/from-csv     — Upload a CSV file and generate (specify row index)
  GET  /generate/sample-input — Download sample trade data JSON

"""

import json
import tempfile
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional

# ─── Routers ──────────────────────────────────────────────────────────────

diff_router     = APIRouter(prefix="/diff",     tags=["Iteration 2 — Diff Engine"])
generate_router = APIRouter(prefix="/generate", tags=["Iteration 3 — Template Populator"])


# ─── Request / Response Models ────────────────────────────────────────────

class CompareByIdRequest(BaseModel):
    template_doc_id: str = Field(..., description="doc_id of the reference template")
    incoming_doc_id: str = Field(..., description="doc_id of the incoming document")

class CompareTextRequest(BaseModel):
    template_text:    str = Field(..., min_length=10, description="Reference template text")
    incoming_text:    str = Field(..., min_length=10, description="Incoming document text")
    template_name:    str = Field("template", description="Label for the template")
    incoming_name:    str = Field("incoming", description="Label for the incoming document")

class GenerateRequest(BaseModel):
    trade_type:        Optional[str] = None
    product:           Optional[str] = None
    counterparty:      Optional[str] = None
    jurisdiction:      Optional[str] = None
    notional_amount:   Optional[str] = None
    currency:          Optional[str] = None
    fixed_rate:        Optional[str] = None
    floating_rate:     Optional[str] = None
    payment_frequency: Optional[str] = None
    effective_date:    Optional[str] = None
    maturity_date:     Optional[str] = None
    day_count:         Optional[str] = None
    governing_law:     Optional[str] = None
    isda_version:      Optional[str] = None
    clearing_venue:    Optional[str] = None
    party_a:           Optional[str] = None
    party_b:           Optional[str] = None
    party_a_role:      Optional[str] = None
    party_b_role:      Optional[str] = None
    trade_date:        Optional[str] = None
    trader_name:       Optional[str] = None
    template_filename: Optional[str] = Field(None, description="Specific base template to use")


# ─── Helpers ──────────────────────────────────────────────────────────────

def _get_vector_store():
    from src.vector_store import get_vector_store
    return get_vector_store()

def _get_extractor():
    from src.diff.field_extractor import FieldExtractor
    return FieldExtractor()

def _get_diff_engine():
    from src.diff.diff_engine import DiffEngine
    return DiffEngine()

def _get_populator():
    from src.generator.template_populator import TemplatePopulator
    return TemplatePopulator()

def _get_text_for_doc_id(doc_id: str) -> tuple[str, str]:
    """Return (full_text, filename) for a stored doc_id."""
    store = _get_vector_store()
    entries = store.list_all()
    entry = next((e for e in entries if e["doc_id"] == doc_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail=f"doc_id not found: {doc_id}")
    return entry.get("full_text", ""), entry.get("filename", doc_id)

def _save_upload_to_tmp(upload: UploadFile) -> Path:
    suffix = Path(upload.filename).suffix.lower()
    allowed = {".docx", ".pdf", ".txt"}
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")
    tmp = Path(tempfile.mktemp(suffix=suffix))
    with open(tmp, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return tmp


# ─── Diff Endpoints ───────────────────────────────────────────────────────

@diff_router.post(
    "/compare",
    summary="Compare two stored templates by doc_id",
    response_description="Full diff report with discrepancies tagged by risk level",
)
async def compare_by_id(request: CompareByIdRequest):
    """
    Compare two documents already stored in the vector store.
    Returns all field discrepancies with risk levels (HIGH/MEDIUM/LOW),
    change types, numeric deltas, and explanations.
    """
    tmpl_text, tmpl_name = _get_text_for_doc_id(request.template_doc_id)
    inc_text,  inc_name  = _get_text_for_doc_id(request.incoming_doc_id)

    extractor = _get_extractor()
    engine    = _get_diff_engine()

    tmpl_doc = extractor.extract_from_text(tmpl_text, tmpl_name)
    inc_doc  = extractor.extract_from_text(inc_text,  inc_name)
    report   = engine.compare(tmpl_doc, inc_doc)

    return JSONResponse(content=report.to_dict())


@diff_router.post(
    "/compare-text",
    summary="Compare two raw text blocks",
)
async def compare_text(request: CompareTextRequest):
    """
    Compare two blocks of plain text directly (no stored templates required).
    Useful for quick ad-hoc comparisons from the UI.
    """
    extractor = _get_extractor()
    engine    = _get_diff_engine()

    tmpl_doc = extractor.extract_from_text(request.template_text, request.template_name)
    inc_doc  = extractor.extract_from_text(request.incoming_text, request.incoming_name)
    report   = engine.compare(tmpl_doc, inc_doc)

    return JSONResponse(content=report.to_dict())


@diff_router.post(
    "/compare-upload",
    summary="Upload two .docx files and compare them",
)
async def compare_upload(
    template_file: UploadFile = File(..., description="Reference template .docx"),
    incoming_file: UploadFile = File(..., description="Incoming document .docx"),
):
    """
    Upload two .docx files directly and receive a full diff report.
    Files are not stored — comparison is done in memory.
    """
    tmp_tmpl = _save_upload_to_tmp(template_file)
    tmp_inc  = _save_upload_to_tmp(incoming_file)

    try:
        engine  = _get_diff_engine()
        report  = engine.compare_files(tmp_tmpl, tmp_inc)
        return JSONResponse(content=report.to_dict())
    finally:
        tmp_tmpl.unlink(missing_ok=True)
        tmp_inc.unlink(missing_ok=True)


# ─── Generate Endpoints ───────────────────────────────────────────────────

@generate_router.post(
    "",
    summary="Generate pre-populated template from trade data",
)
async def generate_from_body(request: GenerateRequest):
    """
    Generate a pre-populated trade confirmation document from structured trade data.

    Three-stage pipeline:
      1. Auto-fill known fields from input data
      2. AI clause suggestions for empty fields (governing law, ISDA, day count, etc.)
      3. Business rule validation

    Returns populated text, validation results, and a download link.
    """
    populator = _get_populator()
    trade_dict = {k: v for k, v in request.dict().items()
                  if k != "template_filename" and v is not None}
    template_filename = request.template_filename

    result = populator.generate(trade_dict, template_filename)

    # Save populated .docx to tmp
    out_dir = Path("data/populated")
    out_dir.mkdir(parents=True, exist_ok=True)
    saved_path = result.save(out_dir / result.filename)

    return {
        "filename":          result.filename,
        "download_url":      f"/generate/download/{result.filename}",
        "populated_text":    result.populated_text,
        "autofill_count":    result.autofill_count,
        "ai_clause_count":   result.ai_clause_count,
        "validation_score":  result.validation_score,
        "is_valid":          result.is_valid,
        "trade_data":        result.trade_data.to_dict(),
        "validation_issues": [
            {
                "field":    i.field,
                "severity": i.severity,
                "message":  i.message,
                "rule_id":  i.rule_id,
            }
            for i in result.issues
        ],
    }


@generate_router.post(
    "/from-json",
    summary="Upload a JSON file and generate populated template",
)
async def generate_from_json_file(
    json_file: UploadFile = File(..., description="JSON file with trade data"),
    template_filename: Optional[str] = Form(None),
):
    tmp = Path(tempfile.mktemp(suffix=".json"))
    try:
        with open(tmp, "wb") as f:
            shutil.copyfileobj(json_file.file, f)
        populator = _get_populator()
        result    = populator.generate_from_file(tmp, )

        out_dir = Path("data/populated")
        out_dir.mkdir(parents=True, exist_ok=True)
        result.save(out_dir / result.filename)

        return {
            "filename":         result.filename,
            "download_url":     f"/generate/download/{result.filename}",
            "autofill_count":   result.autofill_count,
            "ai_clause_count":  result.ai_clause_count,
            "validation_score": result.validation_score,
            "is_valid":         result.is_valid,
            "validation_issues": [
                {"field": i.field, "severity": i.severity,
                 "message": i.message, "rule_id": i.rule_id}
                for i in result.issues
            ],
        }
    finally:
        tmp.unlink(missing_ok=True)


@generate_router.post(
    "/from-csv",
    summary="Upload a CSV file and generate populated template from a row",
)
async def generate_from_csv_file(
    csv_file:  UploadFile = File(..., description="CSV file with trade data"),
    row_index: int        = Form(0, description="Row index (0-based)"),
):
    tmp = Path(tempfile.mktemp(suffix=".csv"))
    try:
        with open(tmp, "wb") as f:
            shutil.copyfileobj(csv_file.file, f)
        populator = _get_populator()
        result    = populator.generate_from_csv(tmp, row=row_index)

        out_dir = Path("data/populated")
        out_dir.mkdir(parents=True, exist_ok=True)
        result.save(out_dir / result.filename)

        return {
            "filename":         result.filename,
            "download_url":     f"/generate/download/{result.filename}",
            "autofill_count":   result.autofill_count,
            "ai_clause_count":  result.ai_clause_count,
            "validation_score": result.validation_score,
            "is_valid":         result.is_valid,
            "validation_issues": [
                {"field": i.field, "severity": i.severity,
                 "message": i.message, "rule_id": i.rule_id}
                for i in result.issues
            ],
        }
    finally:
        tmp.unlink(missing_ok=True)


@generate_router.get(
    "/download/{filename}",
    summary="Download a previously generated .docx file",
)
async def download_generated(filename: str):
    path = Path("data/populated") / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    return FileResponse(
        path=str(path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@generate_router.get(
    "/sample-input",
    summary="Download sample trade data JSON",
)
async def sample_input():
    """Returns a sample JSON payload showing all supported input fields."""
    sample = {
        "trade_type":       "Interest Rate Swap",
        "product":          "Vanilla IRS",
        "counterparty":     "Goldman Sachs",
        "jurisdiction":     "US",
        "currency":         "USD",
        "notional_amount":  "USD 50,000,000",
        "fixed_rate":       "4.25% per annum",
        "payment_frequency":"Quarterly",
        "effective_date":   "April 1, 2026",
        "maturity_date":    "April 1, 2031",
        "party_a":          "Goldman Sachs Bank USA",
        "party_b":          "ABC Capital LLC",
        "trader_name":      "J. Smith",
        "_notes": {
            "optional_fields": ["floating_rate","day_count","governing_law",
                                "isda_version","clearing_venue","trade_date"],
            "auto_suggested":  "governing_law, isda_version, day_count, floating_rate, payment_frequency are auto-filled if omitted",
        }
    }
    return JSONResponse(content=sample)
