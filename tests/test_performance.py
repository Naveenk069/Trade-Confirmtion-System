"""
test_performance.py — Performance and load tests for the Trade Confirmation API.

Tests:
  - Latency benchmarks for all endpoints (p50, p95, p99)
  - Concurrent load testing (10, 50, 100 simultaneous users)
  - Search throughput (queries per second)
  - Ingestion pipeline speed

Run with:
    python tests/test_performance.py

Requires the API running at http://localhost:8000:
    uvicorn src.api.main:app --port 8000
"""

import sys
import time
import statistics
import threading
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

API_BASE = "http://localhost:8000"

try:
    import requests
    SESSION = requests.Session()
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)


# ─── Models ───────────────────────────────────────────────────────────────

@dataclass
class LatencyResult:
    endpoint: str
    method: str
    samples: list[float] = field(default_factory=list)
    errors: int = 0

    @property
    def p50(self): return round(statistics.median(self.samples) * 1000, 1) if self.samples else 0
    @property
    def p95(self):
        if not self.samples: return 0
        s = sorted(self.samples)
        return round(s[int(len(s) * 0.95)] * 1000, 1)
    @property
    def p99(self):
        if not self.samples: return 0
        s = sorted(self.samples)
        return round(s[int(len(s) * 0.99)] * 1000, 1)
    @property
    def mean(self): return round(statistics.mean(self.samples) * 1000, 1) if self.samples else 0
    @property
    def passed(self): return self.p95 < 2000  # SLA: p95 < 2 seconds

    def summary(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return (f"  {status}  {self.method} {self.endpoint}\n"
                f"         mean={self.mean}ms  p50={self.p50}ms  "
                f"p95={self.p95}ms  p99={self.p99}ms  errors={self.errors}")


@dataclass
class LoadResult:
    concurrency: int
    total_requests: int
    successful: int
    failed: int
    duration_seconds: float
    latencies: list[float] = field(default_factory=list)

    @property
    def rps(self): return round(self.successful / self.duration_seconds, 1)
    @property
    def error_rate(self): return round(self.failed / self.total_requests * 100, 1)
    @property
    def p95(self):
        if not self.latencies: return 0
        s = sorted(self.latencies)
        return round(s[int(len(s) * 0.95)] * 1000, 1)
    @property
    def passed(self): return self.error_rate < 5 and self.p95 < 2000


# ─── Helpers ──────────────────────────────────────────────────────────────

def timed_get(path: str) -> tuple[float, int]:
    """Return (elapsed_seconds, status_code)."""
    try:
        start = time.perf_counter()
        r = SESSION.get(f"{API_BASE}{path}", timeout=10)
        return time.perf_counter() - start, r.status_code
    except Exception:
        return 10.0, 0


def timed_post(path: str, payload: dict) -> tuple[float, int]:
    try:
        start = time.perf_counter()
        r = SESSION.post(f"{API_BASE}{path}", json=payload, timeout=10)
        return time.perf_counter() - start, r.status_code
    except Exception:
        return 10.0, 0


def check_api_running() -> bool:
    try:
        r = requests.get(f"{API_BASE}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


SEARCH_QUERIES = [
    "Goldman Sachs interest rate swap USD SOFR fixed floating",
    "FX forward foreign exchange EUR SWIFT settlement",
    "credit default swap CDS protection seller reference entity",
    "equity swap total return S&P 500 Deutsche Bank",
    "SONIA floating rate quarterly UK jurisdiction Citibank",
    "notional amount payment frequency maturity date",
    "ISDA master agreement credit support annex collateral",
    "Barclays protection buyer credit event bankruptcy",
]


# ─── Test 1: Latency Benchmarks ───────────────────────────────────────────

def test_latency_benchmarks(n_samples: int = 30) -> list[LatencyResult]:
    """Measure p50/p95/p99 latency for each endpoint over n_samples calls."""
    print(f"\n  {'─'*56}")
    print(f"  LATENCY BENCHMARKS  ({n_samples} samples each, SLA: p95 < 2000ms)")
    print(f"  {'─'*56}")

    endpoints = [
        ("GET",  "/health",   None),
        ("GET",  "/facets",   None),
        ("GET",  "/templates", None),
        ("POST", "/search",   {"query": "interest rate swap Goldman Sachs USD", "top_k": 5}),
        ("POST", "/search",   {"query": "FX forward EUR settlement", "trade_type": "FX Forward"}),
        ("GET",  "/search/quick?q=credit+default+swap&top_k=3", None),
    ]

    results = []
    for method, path, payload in endpoints:
        result = LatencyResult(endpoint=path, method=method)
        label = f"{method} {path[:45]}"

        for _ in range(n_samples):
            if method == "GET":
                elapsed, status = timed_get(path)
            else:
                elapsed, status = timed_post(path, payload)

            if status == 200:
                result.samples.append(elapsed)
            else:
                result.errors += 1

        results.append(result)
        print(result.summary())

    passed = sum(1 for r in results if r.passed)
    print(f"\n  {'─'*56}")
    print(f"  Latency: {passed}/{len(results)} endpoints meet SLA (p95 < 2s)")
    return results


# ─── Test 2: Concurrent Load Test ─────────────────────────────────────────

def run_load_test(concurrency: int, requests_per_worker: int = 10) -> LoadResult:
    """Simulate concurrent users hitting the search endpoint."""
    total = concurrency * requests_per_worker
    successful = 0
    failed = 0
    latencies = []
    lock = threading.Lock()

    def worker(worker_id: int):
        nonlocal successful, failed
        query = SEARCH_QUERIES[worker_id % len(SEARCH_QUERIES)]
        local_latencies = []
        local_ok = 0
        local_fail = 0

        for _ in range(requests_per_worker):
            elapsed, status = timed_post("/search", {
                "query": query, "top_k": 3
            })
            if status == 200:
                local_ok += 1
                local_latencies.append(elapsed)
            else:
                local_fail += 1

        with lock:
            successful += local_ok
            failed += local_fail
            latencies.extend(local_latencies)

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(worker, i) for i in range(concurrency)]
        for f in as_completed(futures):
            f.result()
    duration = time.perf_counter() - start

    return LoadResult(
        concurrency=concurrency,
        total_requests=total,
        successful=successful,
        failed=failed,
        duration_seconds=round(duration, 2),
        latencies=latencies,
    )


def test_load(concurrency_levels: list[int] = [5, 10, 20]) -> list[LoadResult]:
    print(f"\n  {'─'*56}")
    print(f"  CONCURRENT LOAD TESTS  (10 requests per worker)")
    print(f"  {'─'*56}")
    print(f"  {'Users':<8} {'Requests':<10} {'Success':<10} {'Errors':<8} {'RPS':<8} {'p95':<10} {'Status'}")
    print(f"  {'─'*56}")

    results = []
    for c in concurrency_levels:
        result = run_load_test(concurrency=c, requests_per_worker=10)
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"  {c:<8} {result.total_requests:<10} {result.successful:<10} "
              f"{result.failed:<8} {result.rps:<8} {result.p95}ms{'':<4} {status}")
        results.append(result)

    return results


# ─── Test 3: Search Throughput ────────────────────────────────────────────

def test_search_throughput(duration_seconds: int = 10) -> dict:
    """How many search queries can we handle per second (single-threaded)?"""
    print(f"\n  {'─'*56}")
    print(f"  SEARCH THROUGHPUT  ({duration_seconds}s sustained, single-threaded)")
    print(f"  {'─'*56}")

    completed = 0
    errors = 0
    latencies = []
    start = time.perf_counter()
    query_idx = 0

    while time.perf_counter() - start < duration_seconds:
        query = SEARCH_QUERIES[query_idx % len(SEARCH_QUERIES)]
        elapsed, status = timed_post("/search", {"query": query, "top_k": 5})
        if status == 200:
            completed += 1
            latencies.append(elapsed)
        else:
            errors += 1
        query_idx += 1

    actual_duration = time.perf_counter() - start
    qps = round(completed / actual_duration, 1)
    mean_ms = round(statistics.mean(latencies) * 1000, 1) if latencies else 0

    result = {
        "completed": completed,
        "errors": errors,
        "duration": round(actual_duration, 1),
        "qps": qps,
        "mean_ms": mean_ms,
        "passed": qps >= 5,  # Target: >= 5 QPS
    }

    status = "✅ PASS" if result["passed"] else "❌ FAIL"
    print(f"  Queries completed : {completed}")
    print(f"  Errors            : {errors}")
    print(f"  Throughput        : {qps} QPS  {status}")
    print(f"  Mean latency      : {mean_ms}ms")
    print(f"  Target            : >= 5 QPS")

    return result


# ─── Test 4: Ingestion Speed ──────────────────────────────────────────────

def test_ingestion_speed() -> dict:
    """Measure ingestion pipeline speed (parse + embed + store per doc)."""
    print(f"\n  {'─'*56}")
    print(f"  INGESTION PIPELINE SPEED")
    print(f"  {'─'*56}")

    from src.ingestion_pipeline import IngestionPipeline
    from src.template_generator import generate_all_templates
    from src.config import TEMPLATES_DIR

    generate_all_templates()

    pipeline = IngestionPipeline()
    start = time.perf_counter()
    report = pipeline.run(force=True)
    elapsed = time.perf_counter() - start

    per_doc = round(elapsed / max(report.total_files, 1) * 1000, 1)
    passed = per_doc < 500  # Target: < 500ms per document

    result = {
        "total_docs": report.total_files,
        "ingested": report.ingested,
        "duration_seconds": round(elapsed, 2),
        "ms_per_doc": per_doc,
        "passed": passed,
    }

    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  Documents processed : {report.total_files}")
    print(f"  Total time          : {round(elapsed, 2)}s")
    print(f"  Time per document   : {per_doc}ms  {status}")
    print(f"  Target              : < 500ms per document")

    return result


# ─── Summary ──────────────────────────────────────────────────────────────

def print_summary(latency_results, load_results, throughput, ingest):
    print(f"\n{'='*60}")
    print("  PERFORMANCE TEST SUMMARY")
    print(f"{'='*60}")

    lat_pass = sum(1 for r in latency_results if r.passed)
    load_pass = sum(1 for r in load_results if r.passed)

    checks = [
        (f"Latency SLA ({lat_pass}/{len(latency_results)} endpoints p95 < 2s)",
         lat_pass == len(latency_results)),
        (f"Load test ({load_pass}/{len(load_results)} concurrency levels)",
         load_pass == len(load_results)),
        (f"Search throughput ({throughput['qps']} QPS >= 5 target)",
         throughput["passed"]),
        (f"Ingestion speed ({ingest['ms_per_doc']}ms/doc < 500ms target)",
         ingest["passed"]),
    ]

    all_pass = all(c[1] for c in checks)
    for label, passed in checks:
        icon = "✅" if passed else "❌"
        print(f"  {icon}  {label}")

    print(f"\n  Overall: {'✅ ALL TESTS PASSED' if all_pass else '⚠ SOME TESTS FAILED'}")
    print(f"{'='*60}\n")


# ─── Main ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  PHASE 4 — PERFORMANCE TESTS")
    print("  Trade Confirmation Automation System")
    print("="*60)

    if not check_api_running():
        print(f"\n  ❌ API not running at {API_BASE}")
        print("  Start it with: uvicorn src.api.main:app --port 8000\n")
        sys.exit(1)

    print(f"\n  ✅ API is running at {API_BASE}")

    latency_results = test_latency_benchmarks(n_samples=20)
    load_results    = test_load(concurrency_levels=[5, 10, 20])
    throughput      = test_search_throughput(duration_seconds=10)
    ingest          = test_ingestion_speed()

    print_summary(latency_results, load_results, throughput, ingest)
