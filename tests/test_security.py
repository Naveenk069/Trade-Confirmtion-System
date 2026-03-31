"""
test_security.py — Security hardening tests for the Trade Confirmation API.

Covers:
  1. Input validation — malformed, oversized, and injected inputs
  2. SQL / NoSQL injection attempts
  3. Path traversal attacks
  4. PII detection in stored templates
  5. File upload security (malicious file types, oversized uploads)
  6. HTTP method enforcement
  7. Response header security checks
  8. Rate limiting awareness

Run with:
    python tests/test_security.py

Requires the API running at http://localhost:8000
"""

import sys
import json
import io
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

API_BASE = "http://localhost:8000"

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)


# ─── Helpers ──────────────────────────────────────────────────────────────

def check_api_running() -> bool:
    try:
        return requests.get(f"{API_BASE}/health", timeout=3).status_code == 200
    except Exception:
        return False


passed_count = 0
failed_count = 0


def check(name: str, condition: bool, detail: str = ""):
    global passed_count, failed_count
    if condition:
        passed_count += 1
        print(f"  ✅  {name}")
    else:
        failed_count += 1
        print(f"  ❌  {name}" + (f"\n      → {detail}" if detail else ""))


# ─── 1. Input Validation ──────────────────────────────────────────────────

def test_input_validation():
    print(f"\n  {'─'*56}")
    print("  1. INPUT VALIDATION")
    print(f"  {'─'*56}")

    # Empty query
    r = requests.post(f"{API_BASE}/search", json={"query": ""})
    check("Empty query rejected (422)", r.status_code == 422)

    # Whitespace-only query
    r = requests.post(f"{API_BASE}/search", json={"query": "   "})
    check("Whitespace-only query rejected (422)", r.status_code == 422)

    # Query too short
    r = requests.post(f"{API_BASE}/search", json={"query": "a"})
    check("Query < 2 chars rejected (422)", r.status_code == 422)

    # Query too long (> 500 chars)
    r = requests.post(f"{API_BASE}/search", json={"query": "x" * 501})
    check("Query > 500 chars rejected (422)", r.status_code == 422)

    # top_k out of range
    r = requests.post(f"{API_BASE}/search", json={"query": "swap", "top_k": 0})
    check("top_k=0 rejected (422)", r.status_code == 422)

    r = requests.post(f"{API_BASE}/search", json={"query": "swap", "top_k": 999})
    check("top_k=999 rejected (422)", r.status_code == 422)

    # Missing required field
    r = requests.post(f"{API_BASE}/search", json={"top_k": 5})
    check("Missing query field rejected (422)", r.status_code == 422)

    # Wrong content type (form instead of JSON)
    r = requests.post(f"{API_BASE}/search",
                      data="query=swap",
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
    check("Wrong content-type rejected (422)", r.status_code == 422)

    # Valid edge case — exactly 2 chars
    r = requests.post(f"{API_BASE}/search", json={"query": "IR"})
    check("Minimum valid query (2 chars) accepted (200)", r.status_code == 200)


# ─── 2. Injection Attacks ─────────────────────────────────────────────────

def test_injection_attacks():
    print(f"\n  {'─'*56}")
    print("  2. INJECTION ATTACK PREVENTION")
    print(f"  {'─'*56}")

    injection_payloads = [
        ("SQL injection",        "' OR 1=1 --; DROP TABLE templates;"),
        ("NoSQL injection",      '{"$gt": ""}'),
        ("Script injection",     "<script>alert('xss')</script>"),
        ("Command injection",    "; rm -rf / #"),
        ("LDAP injection",       "*)(uid=*))(|(uid=*"),
        ("Template injection",   "{{7*7}} ${7*7} #{7*7}"),
        ("Path traversal query", "../../etc/passwd"),
        ("Null bytes",           "swap\x00malicious"),
    ]

    for name, payload in injection_payloads:
        r = requests.post(f"{API_BASE}/search", json={"query": payload})
        # Should return 200 (handled gracefully) or 422 (rejected) — never 500
        check(
            f"{name} doesn't cause 500 error",
            r.status_code in (200, 422, 400),
            f"Got {r.status_code}: {r.text[:100]}"
        )

    # Path traversal in doc_id
    traversal_ids = [
        "../../../etc/passwd",
        "..%2F..%2Fetc%2Fpasswd",
        "%2e%2e%2fetc%2fpasswd",
    ]
    for tid in traversal_ids:
        r = requests.get(f"{API_BASE}/templates/{tid}")
        check(
            f"Path traversal in doc_id returns 404 not file contents",
            r.status_code in (404, 422, 400),
            f"Got {r.status_code}"
        )


# ─── 3. File Upload Security ──────────────────────────────────────────────

def test_file_upload_security():
    print(f"\n  {'─'*56}")
    print("  3. FILE UPLOAD SECURITY")
    print(f"  {'─'*56}")

    # Executable file disguised as docx
    r = requests.post(
        f"{API_BASE}/ingest/file",
        files={"file": ("malware.exe", b"MZ fake executable", "application/octet-stream")},
        data={"force": "false"},
    )
    check(".exe file rejected (400)", r.status_code == 400)

    # PHP file
    r = requests.post(
        f"{API_BASE}/ingest/file",
        files={"file": ("shell.php", b"<?php system($_GET['cmd']); ?>", "text/plain")},
        data={"force": "false"},
    )
    check(".php file rejected (400)", r.status_code == 400)

    # JavaScript file
    r = requests.post(
        f"{API_BASE}/ingest/file",
        files={"file": ("exploit.js", b"require('child_process').exec('rm -rf /')", "text/javascript")},
        data={"force": "false"},
    )
    check(".js file rejected (400)", r.status_code == 400)

    # Zip bomb (simulate — just large content)
    large_content = b"A" * (1024 * 100)  # 100KB fake content
    r = requests.post(
        f"{API_BASE}/ingest/file",
        files={"file": ("large.txt", large_content, "text/plain")},
        data={"force": "false"},
    )
    check("Large .txt upload handled without crash (200/400/500 not hang)",
          r.status_code in (200, 400, 422, 500))

    # Double extension
    r = requests.post(
        f"{API_BASE}/ingest/file",
        files={"file": ("template.docx.exe", b"fake", "application/octet-stream")},
        data={"force": "false"},
    )
    check("Double extension .docx.exe rejected (400)", r.status_code == 400)


# ─── 4. HTTP Method Enforcement ───────────────────────────────────────────

def test_http_method_enforcement():
    print(f"\n  {'─'*56}")
    print("  4. HTTP METHOD ENFORCEMENT")
    print(f"  {'─'*56}")

    # GET on POST-only endpoint
    r = requests.get(f"{API_BASE}/search")
    check("GET /search returns 405 Method Not Allowed", r.status_code == 405)

    # DELETE on read-only endpoint
    r = requests.delete(f"{API_BASE}/health")
    check("DELETE /health returns 405", r.status_code == 405)

    # PUT not supported
    r = requests.put(f"{API_BASE}/search", json={"query": "test"})
    check("PUT /search returns 405", r.status_code == 405)

    # PATCH not supported
    r = requests.patch(f"{API_BASE}/templates")
    check("PATCH /templates returns 405", r.status_code == 405)


# ─── 5. Response Header Security ──────────────────────────────────────────

def test_response_headers():
    print(f"\n  {'─'*56}")
    print("  5. RESPONSE HEADERS")
    print(f"  {'─'*56}")

    r = requests.get(f"{API_BASE}/health")
    headers = {k.lower(): v for k, v in r.headers.items()}

    # Custom timing header (added by our middleware)
    check("X-Process-Time-Ms header present",
          "x-process-time-ms" in headers)

    # Content type
    check("Content-Type is application/json",
          "application/json" in headers.get("content-type", ""))

    # Should NOT expose internal server details
    server_header = headers.get("server", "").lower()
    check("Server header doesn't expose uvicorn version details",
          "uvicorn" not in server_header or "/" not in server_header)

    # API should not return stack traces in production responses
    r2 = requests.get(f"{API_BASE}/templates/nonexistent-id")
    check("404 response doesn't expose stack trace",
          "traceback" not in r2.text.lower() and
          "file \"/" not in r2.text.lower())


# ─── 6. PII Detection in Templates ───────────────────────────────────────

def test_pii_detection():
    """
    Scan stored template text for common PII patterns.
    This is a compliance check — templates should not contain real PII.
    """
    print(f"\n  {'─'*56}")
    print("  6. PII DETECTION IN STORED TEMPLATES")
    print(f"  {'─'*56}")

    PII_PATTERNS = {
        "SSN":          r"\b\d{3}-\d{2}-\d{4}\b",
        "Credit Card":  r"\b(?:\d{4}[\s\-]?){3}\d{4}\b",
        "Email":        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "Phone (US)":   r"\b(\+1[\s\-]?)?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}\b",
        "Passport":     r"\b[A-Z]{1,2}\d{6,9}\b",
    }

    r = requests.get(f"{API_BASE}/templates?active_only=false")
    if r.status_code != 200:
        print("  ⚠  Could not fetch templates for PII scan")
        return

    templates = r.json().get("templates", [])
    pii_found = []

    for t in templates:
        detail_r = requests.get(f"{API_BASE}/templates/{t['doc_id']}")
        if detail_r.status_code != 200:
            continue
        text = detail_r.json().get("full_text", "")

        for pii_type, pattern in PII_PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                pii_found.append({
                    "file": t["filename"],
                    "type": pii_type,
                    "count": len(matches),
                })

    check(f"No SSNs found in templates",
          not any(p["type"] == "SSN" for p in pii_found))
    check(f"No credit card numbers found",
          not any(p["type"] == "Credit Card" for p in pii_found))
    check(f"No personal email addresses found",
          not any(p["type"] == "Email" for p in pii_found))

    if pii_found:
        print(f"\n  ⚠  PII findings (review required):")
        for p in pii_found:
            print(f"     {p['file']}: {p['type']} ({p['count']} occurrence(s))")
    else:
        print("  ℹ  No PII patterns detected in any template")


# ─── 7. Error Handling ────────────────────────────────────────────────────

def test_error_handling():
    print(f"\n  {'─'*56}")
    print("  7. ERROR HANDLING & INFORMATION LEAKAGE")
    print(f"  {'─'*56}")

    # Non-existent endpoint
    r = requests.get(f"{API_BASE}/nonexistent_endpoint_xyz")
    check("404 for unknown endpoint (not 500)",
          r.status_code == 404)

    # Malformed JSON body
    r = requests.post(
        f"{API_BASE}/search",
        data="{invalid json{{",
        headers={"Content-Type": "application/json"}
    )
    check("Malformed JSON body returns 422 not 500",
          r.status_code in (422, 400))

    # Very deeply nested JSON
    nested = {"query": "test"}
    for _ in range(50):
        nested = {"nested": nested}
    r = requests.post(f"{API_BASE}/search", json=nested)
    check("Deeply nested JSON handled gracefully (not 500)",
          r.status_code in (200, 422, 400))

    # Unicode edge cases
    unicode_queries = ["测试 interest rate swap", "IRS café Zürich", "swap\u202e reversed"]
    for q in unicode_queries:
        r = requests.post(f"{API_BASE}/search", json={"query": q})
        check(f"Unicode query handled ({q[:20]}…)",
              r.status_code in (200, 422))


# ─── Summary ──────────────────────────────────────────────────────────────

def print_summary():
    total = passed_count + failed_count
    print(f"\n{'='*60}")
    print("  SECURITY TEST SUMMARY")
    print(f"{'='*60}")
    print(f"  Passed : {passed_count}/{total}")
    print(f"  Failed : {failed_count}/{total}")
    if failed_count == 0:
        print("  Result : ✅ ALL SECURITY CHECKS PASSED")
    else:
        print("  Result : ⚠  SECURITY ISSUES FOUND — review failures above")
    print(f"{'='*60}\n")

    print("  Recommended hardening steps for production:")
    hardening = [
        "Add JWT/OAuth2 authentication to all endpoints",
        "Enable HTTPS/TLS (never run HTTP in production)",
        "Set Content-Security-Policy and X-Frame-Options headers",
        "Add rate limiting (e.g. slowapi: 100 req/min per IP)",
        "Implement file size limit (50MB) in FastAPI middleware",
        "Scan uploaded files with antivirus before ingestion",
        "Store API keys in environment variables / secrets manager",
        "Add audit logging for all ingest and delete operations",
    ]
    for item in hardening:
        print(f"  → {item}")
    print()


# ─── Main ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  PHASE 4 — SECURITY TESTS")
    print("  Trade Confirmation Automation System")
    print("="*60)

    if not check_api_running():
        print(f"\n  ❌ API not running at {API_BASE}")
        print("  Start it with: uvicorn src.api.main:app --port 8000\n")
        sys.exit(1)

    print(f"\n  ✅ API is running at {API_BASE}")

    test_input_validation()
    test_injection_attacks()
    test_file_upload_security()
    test_http_method_enforcement()
    test_response_headers()
    test_pii_detection()
    test_error_handling()

    print_summary()
