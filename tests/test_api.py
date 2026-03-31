"""
test_api.py — API endpoint tests using FastAPI's TestClient.

Tests every endpoint without needing a running server.
Run with: python tests/test_api.py
      or: python -m pytest tests/test_api.py -v
"""

import sys
import json
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from src.api.main import app
from src.template_generator import generate_all_templates
from src.config import TEMPLATES_DIR

# Generate templates before any tests run
generate_all_templates()

client = TestClient(app)


# ─── /health ──────────────────────────────────────────────────────────────

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["templates_in_store"] >= 8
    assert "embedding_backend" in data
    assert "timestamp" in data
    print(f"  ✅ GET /health — {data['templates_in_store']} templates, backend={data['embedding_backend']}")


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "docs" in response.json()
    print("  ✅ GET / — root endpoint OK")


# ─── /search ──────────────────────────────────────────────────────────────

def test_search_basic():
    response = client.post("/search", json={
        "query": "interest rate swap Goldman Sachs USD SOFR"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["total_results"] > 0
    assert data["results"][0]["score"] > 0
    assert "filename" in data["results"][0]
    print(f"  ✅ POST /search — {data['total_results']} results, top score={data['results'][0]['score']:.3f}")


def test_search_with_filters():
    response = client.post("/search", json={
        "query": "interest rate swap SONIA floating",
        "jurisdiction": "UK",
        "top_k": 5,
    })
    assert response.status_code == 200
    data = response.json()
    # All results must be from UK
    for result in data["results"]:
        assert result["jurisdiction"] == "UK", f"Expected UK, got {result['jurisdiction']}"
    print(f"  ✅ POST /search (filtered UK) — {data['total_results']} results, all UK")


def test_search_returns_ranked_results():
    """IRS query should return IRS templates ranked higher than FX templates."""
    response = client.post("/search", json={
        "query": "interest rate swap fixed rate SOFR notional USD",
        "top_k": 8,
    })
    assert response.status_code == 200
    results = response.json()["results"]
    top_3_types = [r["trade_type"] for r in results[:3]]
    assert "Interest Rate Swap" in top_3_types, f"IRS should be in top 3: {top_3_types}"
    print(f"  ✅ POST /search ranking — top 3 types: {top_3_types}")


def test_search_empty_query_rejected():
    response = client.post("/search", json={"query": "   "})
    assert response.status_code == 422  # Pydantic validation error
    print("  ✅ POST /search — blank query correctly rejected (422)")


def test_search_top_k_limit():
    response = client.post("/search", json={"query": "swap", "top_k": 3})
    assert response.status_code == 200
    assert len(response.json()["results"]) <= 3
    print("  ✅ POST /search — top_k=3 respected")


def test_search_quick_get():
    response = client.get("/search/quick?q=FX+forward+SWIFT+settlement&top_k=3")
    assert response.status_code == 200
    data = response.json()
    assert data["total_results"] > 0
    print(f"  ✅ GET /search/quick — {data['total_results']} results")


def test_search_response_time_header():
    response = client.post("/search", json={"query": "credit default swap"})
    assert "x-process-time-ms" in response.headers
    print(f"  ✅ X-Process-Time-Ms header present: {response.headers['x-process-time-ms']}ms")


# ─── /templates ───────────────────────────────────────────────────────────

def test_list_templates():
    response = client.get("/templates")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 8
    assert len(data["templates"]) >= 8
    assert "filename" in data["templates"][0]
    print(f"  ✅ GET /templates — {data['total']} templates listed")


def test_list_templates_filter_by_jurisdiction():
    response = client.get("/templates?jurisdiction=US")
    assert response.status_code == 200
    data = response.json()
    for t in data["templates"]:
        assert t["jurisdiction"] == "US"
    print(f"  ✅ GET /templates?jurisdiction=US — {data['total']} US templates")


def test_get_template_detail():
    # Get a valid doc_id first
    list_response = client.get("/templates?active_only=false")
    templates = list_response.json()["templates"]
    assert len(templates) > 0

    doc_id = templates[0]["doc_id"]
    filename = templates[0]["filename"]

    response = client.get(f"/templates/{doc_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["doc_id"] == doc_id
    assert data["filename"] == filename
    assert len(data["full_text"]) > 50
    print(f"  ✅ GET /templates/{{doc_id}} — detail retrieved for {filename}")


def test_get_template_not_found():
    response = client.get("/templates/nonexistent-doc-id-xyz")
    assert response.status_code == 404
    print("  ✅ GET /templates/{{doc_id}} — 404 for unknown doc_id")


def test_download_template():
    list_response = client.get("/templates")
    doc_id = list_response.json()["templates"][0]["doc_id"]

    response = client.get(f"/templates/{doc_id}/download")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument"
    )
    print(f"  ✅ GET /templates/{{doc_id}}/download — .docx streamed successfully")


# ─── /ingest ──────────────────────────────────────────────────────────────

def test_ingest_file_upload():
    """Upload an existing template file and verify it's ingested."""
    # Use an existing template file as our upload
    template_path = TEMPLATES_DIR / "IRS_GoldmanSachs_USD_v1.docx"
    assert template_path.exists(), f"Template not found: {template_path}"

    with open(template_path, "rb") as f:
        response = client.post(
            "/ingest/file",
            files={"file": ("IRS_GoldmanSachs_USD_v1.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"force": "true"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True or data["skipped"] is True
    assert data["filename"] == "IRS_GoldmanSachs_USD_v1.docx"
    print(f"  ✅ POST /ingest/file — {data['message']}")


def test_ingest_unsupported_file_type():
    response = client.post(
        "/ingest/file",
        files={"file": ("bad_file.exe", b"fake content", "application/octet-stream")},
        data={"force": "false"},
    )
    assert response.status_code == 400
    print("  ✅ POST /ingest/file — unsupported file type rejected (400)")


def test_ingest_refresh():
    response = client.post("/ingest/refresh?force=false")
    assert response.status_code == 200
    data = response.json()
    assert "total_found" in data
    assert "ingested" in data
    assert "skipped" in data
    assert data["failed"] == 0
    print(f"  ✅ POST /ingest/refresh — found={data['total_found']}, ingested={data['ingested']}, skipped={data['skipped']}")


# ─── /facets ──────────────────────────────────────────────────────────────

def test_get_facets():
    response = client.get("/facets")
    assert response.status_code == 200
    data = response.json()
    assert "trade_types" in data
    assert "jurisdictions" in data
    assert "products" in data
    assert "counterparties" in data
    assert "total_templates" in data
    assert "Interest Rate Swap" in data["trade_types"]
    assert "FX Forward" in data["trade_types"]
    assert data["total_templates"] >= 8
    print(f"  ✅ GET /facets — trade_types={data['trade_types']}, total={data['total_templates']}")


# ─── /templates DELETE ────────────────────────────────────────────────────

def test_delete_template():
    """Delete a draft template and verify it's removed."""
    # Find the BNP Paribas draft template
    list_response = client.get("/templates?active_only=false")
    templates = list_response.json()["templates"]
    draft = next((t for t in templates if "BNP" in t["filename"]), None)

    if not draft:
        print("  ⏭  DELETE /templates/{doc_id} — no draft found to delete, skipping")
        return

    doc_id = draft["doc_id"]
    response = client.delete(f"/templates/{doc_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True
    print(f"  ✅ DELETE /templates/{{doc_id}} — deleted '{data['filename']}'")

    # Verify it's gone
    verify = client.get(f"/templates/{doc_id}")
    assert verify.status_code == 404
    print("  ✅ DELETE verified — template no longer accessible")


def test_delete_nonexistent_template():
    response = client.delete("/templates/does-not-exist-xyz")
    assert response.status_code == 404
    print("  ✅ DELETE /templates/{doc_id} — 404 for unknown doc_id")


# ─── Test Runner ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_health_check,
        test_root,
        test_search_basic,
        test_search_with_filters,
        test_search_returns_ranked_results,
        test_search_empty_query_rejected,
        test_search_top_k_limit,
        test_search_quick_get,
        test_search_response_time_header,
        test_list_templates,
        test_list_templates_filter_by_jurisdiction,
        test_get_template_detail,
        test_get_template_not_found,
        test_download_template,
        test_ingest_file_upload,
        test_ingest_unsupported_file_type,
        test_ingest_refresh,
        test_get_facets,
        test_delete_template,
        test_delete_nonexistent_template,
    ]

    print("\n" + "="*60)
    print("  API TEST SUITE")
    print("="*60 + "\n")

    passed = 0
    failed = 0
    for test_fn in tests:
        print(f"  ▶ {test_fn.__name__}")
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        print()

    print("="*60)
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("="*60 + "\n")

    if failed > 0:
        sys.exit(1)
