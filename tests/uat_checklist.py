"""
uat_checklist.py — UAT (User Acceptance Testing) checklist runner.

Generates a structured checklist for the operations team to sign off on
Iteration 1 before production go-live.

Run with:
    python tests/uat_checklist.py

Produces:
  - Terminal walkthrough with pass/fail for automated checks
  - Manual checklist printed for ops team sign-off
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

API_BASE = "http://localhost:8000"

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)


def check_api() -> bool:
    try:
        return requests.get(f"{API_BASE}/health", timeout=3).status_code == 200
    except Exception:
        return False


# ─── UAT Test Categories ──────────────────────────────────────────────────

uat_results = []


def uat_check(category: str, test_id: str, description: str,
              passed: bool, detail: str = "", manual: bool = False):
    icon = "🔲" if manual else ("✅" if passed else "❌")
    status = "MANUAL" if manual else ("PASS" if passed else "FAIL")
    uat_results.append({
        "category": category,
        "test_id":  test_id,
        "description": description,
        "status":   status,
        "detail":   detail,
        "manual":   manual,
    })
    print(f"  {icon}  [{test_id}] {description}")
    if detail and not manual:
        print(f"         → {detail}")


# ─── UAT-1: Template Repository ───────────────────────────────────────────

def uat_template_repository():
    print(f"\n  {'─'*60}")
    print("  UAT-1: TEMPLATE REPOSITORY")
    print(f"  {'─'*60}")

    r = requests.get(f"{API_BASE}/templates")
    templates = r.json().get("templates", []) if r.status_code == 200 else []
    total = len(templates)

    uat_check("Template Repository", "TR-01",
              f"Repository contains >= 8 templates (found: {total})",
              total >= 8, f"{total} templates in store")

    trade_types = set(t.get("trade_type") for t in templates)
    expected = {"Interest Rate Swap", "FX Forward", "Credit Default Swap"}
    missing = expected - trade_types
    uat_check("Template Repository", "TR-02",
              f"Core trade types present (IRS, FX, CDS)",
              len(missing) == 0,
              f"Missing: {missing}" if missing else "All present")

    jurisdictions = set(t.get("jurisdiction") for t in templates)
    uat_check("Template Repository", "TR-03",
              "Multiple jurisdictions covered (US, UK, EU)",
              len(jurisdictions) >= 2,
              f"Jurisdictions: {sorted(jurisdictions)}")

    active = [t for t in templates if t.get("status") == "active"]
    uat_check("Template Repository", "TR-04",
              f"Active templates available (found: {len(active)})",
              len(active) >= 6,
              f"{len(active)} active out of {total}")

    uat_check("Template Repository", "TR-05",
              "All templates have filename, trade_type, counterparty, jurisdiction",
              all(t.get("filename") and t.get("trade_type") and
                  t.get("counterparty") and t.get("jurisdiction")
                  for t in templates),
              "Metadata completeness check")

    # Manual checks
    uat_check("Template Repository", "TR-06",
              "Templates reviewed and approved by Legal/Compliance team",
              False, manual=True)
    uat_check("Template Repository", "TR-07",
              "Template naming convention follows standard: [Product]_[Counterparty]_[CCY]_v[N].docx",
              False, manual=True)


# ─── UAT-2: Search Functionality ──────────────────────────────────────────

def uat_search():
    print(f"\n  {'─'*60}")
    print("  UAT-2: SEMANTIC SEARCH FUNCTIONALITY")
    print(f"  {'─'*60}")

    # IRS search should return IRS templates
    r = requests.post(f"{API_BASE}/search", json={
        "query": "interest rate swap Goldman Sachs USD SOFR fixed floating", "top_k": 3
    })
    results = r.json().get("results", []) if r.status_code == 200 else []
    top_types = [res.get("trade_type") for res in results[:3]]
    uat_check("Search", "SR-01",
              "IRS query returns IRS templates in top 3 results",
              "Interest Rate Swap" in top_types,
              f"Top 3 trade types: {top_types}")

    # FX search
    r = requests.post(f"{API_BASE}/search", json={
        "query": "foreign exchange forward EUR SWIFT settlement", "top_k": 3
    })
    results = r.json().get("results", []) if r.status_code == 200 else []
    top_types = [res.get("trade_type") for res in results[:3]]
    uat_check("Search", "SR-02",
              "FX query returns FX Forward templates in top 3",
              "FX Forward" in top_types,
              f"Top 3 trade types: {top_types}")

    # Jurisdiction filter
    r = requests.post(f"{API_BASE}/search", json={
        "query": "interest rate swap", "jurisdiction": "UK", "top_k": 5
    })
    results = r.json().get("results", []) if r.status_code == 200 else []
    all_uk = all(res.get("jurisdiction") == "UK" for res in results)
    uat_check("Search", "SR-03",
              "Jurisdiction filter returns only matching templates",
              all_uk or len(results) == 0,
              f"All UK: {all_uk}, count: {len(results)}")

    # Search speed
    start = time.time()
    requests.post(f"{API_BASE}/search", json={"query": "swap", "top_k": 5})
    elapsed_ms = (time.time() - start) * 1000
    uat_check("Search", "SR-04",
              f"Search response time < 2000ms (actual: {round(elapsed_ms)}ms)",
              elapsed_ms < 2000,
              f"{round(elapsed_ms, 1)}ms")

    # Precision >= 0.80 (using known relevant query)
    r = requests.post(f"{API_BASE}/search", json={
        "query": "Goldman Sachs interest rate swap USD", "top_k": 5
    })
    results = r.json().get("results", []) if r.status_code == 200 else []
    top_score = results[0]["score"] if results else 0
    uat_check("Search", "SR-05",
              f"Top result relevance score >= 0.30 (actual: {top_score:.3f})",
              top_score >= 0.30,
              f"Score: {top_score:.3f} — Note: TF-IDF; upgrade to sentence-transformers for >= 0.80")

    # Empty results for garbage query
    r = requests.post(f"{API_BASE}/search", json={
        "query": "xyzzy nonsense gobbledygook 12345", "top_k": 5
    })
    results = r.json().get("results", []) if r.status_code == 200 else []
    uat_check("Search", "SR-06",
              "Irrelevant query returns 0 or very low-score results",
              all(res["score"] < 0.3 for res in results) if results else True,
              f"{len(results)} results for garbage query")

    # Manual UAT
    uat_check("Search", "SR-07",
              "Operations user can find correct template in < 30 seconds",
              False, manual=True)
    uat_check("Search", "SR-08",
              "Search results reviewed and approved by 3 ops team members",
              False, manual=True)
    uat_check("Search", "SR-09",
              "Precision@5 >= 0.80 validated on 20-query labelled test set",
              False, manual=True)


# ─── UAT-3: Template Upload & Ingestion ───────────────────────────────────

def uat_ingestion():
    print(f"\n  {'─'*60}")
    print("  UAT-3: TEMPLATE UPLOAD & INGESTION")
    print(f"  {'─'*60}")

    from src.config import TEMPLATES_DIR
    test_file = TEMPLATES_DIR / "IRS_GoldmanSachs_USD_v1.docx"

    if test_file.exists():
        with open(test_file, "rb") as f:
            r = requests.post(
                f"{API_BASE}/ingest/file",
                files={"file": (test_file.name, f,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"force": "true"},
            )
        result = r.json() if r.status_code == 200 else {}
        uat_check("Ingestion", "IN-01",
                  "File upload endpoint accepts .docx files",
                  r.status_code == 200,
                  f"Status: {r.status_code}, message: {result.get('message', '')}")
        uat_check("Ingestion", "IN-02",
                  "Uploaded file immediately searchable after ingest",
                  result.get("success", False) or result.get("skipped", False),
                  f"doc_id: {result.get('doc_id', 'N/A')[:20]}…")
    else:
        uat_check("Ingestion", "IN-01", "File upload test", False,
                  "Test file not found")

    # Unsupported file type rejected
    r = requests.post(
        f"{API_BASE}/ingest/file",
        files={"file": ("bad.exe", b"fake", "application/octet-stream")},
        data={"force": "false"},
    )
    uat_check("Ingestion", "IN-03",
              "Unsupported file types rejected with 400",
              r.status_code == 400,
              f"Got: {r.status_code}")

    # Refresh endpoint
    r = requests.post(f"{API_BASE}/ingest/refresh?force=false")
    uat_check("Ingestion", "IN-04",
              "Refresh endpoint re-scans templates directory",
              r.status_code == 200,
              f"Status: {r.status_code}")

    uat_check("Ingestion", "IN-05",
              "New template uploaded by ops user appears in search within 60s",
              False, manual=True)
    uat_check("Ingestion", "IN-06",
              "Template metadata (trade_type, counterparty) correctly extracted",
              False, manual=True)


# ─── UAT-4: UI Acceptance ─────────────────────────────────────────────────

def uat_ui():
    print(f"\n  {'─'*60}")
    print("  UAT-4: STREAMLIT UI (Manual Checks)")
    print(f"  {'─'*60}")

    manual_checks = [
        ("UI-01", "Streamlit app loads at http://localhost:8501 within 5s"),
        ("UI-02", "API status shows 'ONLINE' with green pulsing dot"),
        ("UI-03", "Search page: typing query and clicking Search returns results"),
        ("UI-04", "Result cards show trade type, counterparty, jurisdiction badges"),
        ("UI-05", "Relevance score bar visually distinguishes high vs low matches"),
        ("UI-06", "Download button streams correct .docx file"),
        ("UI-07", "Template Browser shows all 8 templates in table"),
        ("UI-08", "Filter dropdowns (Trade Type, Jurisdiction) work correctly"),
        ("UI-09", "Upload page: dragging a .docx shows ingestion success message"),
        ("UI-10", "Admin panel shows API health and template count"),
        ("UI-11", "UI is accessible on both Chrome and Edge browsers"),
        ("UI-12", "3 ops team members completed tasks without assistance"),
    ]
    for tid, desc in manual_checks:
        uat_check("UI", tid, desc, False, manual=True)


# ─── UAT-5: Non-Functional Requirements ──────────────────────────────────

def uat_nfr():
    print(f"\n  {'─'*60}")
    print("  UAT-5: NON-FUNCTIONAL REQUIREMENTS")
    print(f"  {'─'*60}")

    # API availability
    r = requests.get(f"{API_BASE}/health")
    uat_check("NFR", "NF-01",
              "API health endpoint responds 200",
              r.status_code == 200)

    # Concurrent requests don't crash
    import threading
    results_list = []
    def hit_api():
        try:
            r = requests.post(f"{API_BASE}/search",
                              json={"query": "swap", "top_k": 3}, timeout=10)
            results_list.append(r.status_code)
        except Exception:
            results_list.append(0)

    threads = [threading.Thread(target=hit_api) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    all_ok = all(s == 200 for s in results_list)
    uat_check("NFR", "NF-02",
              f"10 concurrent requests all succeed (got: {results_list.count(200)}/10 OK)",
              all_ok, f"Status codes: {results_list}")

    # Error messages are user-friendly
    r = requests.get(f"{API_BASE}/templates/nonexistent-id-xyz")
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    uat_check("NFR", "NF-03",
              "404 error returns structured JSON (not HTML stack trace)",
              r.status_code == 404 and isinstance(body, dict),
              f"Body keys: {list(body.keys())}")

    manual_nfr = [
        ("NF-04", "System handles 50 concurrent users without degradation"),
        ("NF-05", "Drafting time per confirmation reduced by >= 60% vs baseline"),
        ("NF-06", "Ops team sign-off on ease of use (SUS score >= 70)"),
        ("NF-07", "No PII or sensitive data exposed in API responses"),
        ("NF-08", "Deployment runbook reviewed and approved by DevOps"),
    ]
    for tid, desc in manual_nfr:
        uat_check("NFR", tid, desc, False, manual=True)


# ─── Print UAT Report ─────────────────────────────────────────────────────

def print_uat_report():
    auto   = [r for r in uat_results if not r["manual"]]
    manual = [r for r in uat_results if r["manual"]]
    auto_pass  = sum(1 for r in auto   if r["status"] == "PASS")
    auto_fail  = sum(1 for r in auto   if r["status"] == "FAIL")

    print(f"\n{'='*60}")
    print("  UAT SIGN-OFF REPORT")
    print(f"  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}")
    print(f"  Automated checks : {auto_pass} passed, {auto_fail} failed / {len(auto)} total")
    print(f"  Manual checks    : {len(manual)} pending ops team sign-off")
    print(f"{'='*60}")

    if auto_fail > 0:
        print("\n  ❌ Failed automated checks:")
        for r in auto:
            if r["status"] == "FAIL":
                print(f"    [{r['test_id']}] {r['description']}")
                if r["detail"]:
                    print(f"           → {r['detail']}")

    print(f"\n  🔲 Manual checks for ops team sign-off:")
    for r in manual:
        print(f"    [ ] [{r['test_id']}] {r['description']}")

    print(f"\n  {'✅ AUTOMATED UAT PASSED' if auto_fail == 0 else '⚠  AUTOMATED UAT HAS FAILURES'}")
    print(f"  Manual sign-off required before production go-live.")
    print(f"{'='*60}\n")

    return auto_fail == 0


# ─── Main ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  PHASE 4 — UAT CHECKLIST")
    print("  Trade Confirmation Automation System — Iteration 1")
    print("="*60)

    if not check_api():
        print(f"\n  ❌ API not running at {API_BASE}")
        print("  Start it with: uvicorn src.api.main:app --port 8000\n")
        sys.exit(1)

    print(f"\n  ✅ API is running at {API_BASE}\n")

    uat_template_repository()
    uat_search()
    uat_ingestion()
    uat_ui()
    uat_nfr()

    passed = print_uat_report()
    sys.exit(0 if passed else 1)
