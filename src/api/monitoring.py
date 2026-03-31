"""
monitoring.py — Monitoring, structured logging, and metrics for the API.

Features:
  - Structured JSON logging (every request logged with timing + metadata)
  - In-memory metrics store (request counts, latency histograms, error rates)
  - /metrics endpoint (Prometheus-compatible text format)
  - /stats endpoint (JSON dashboard summary)
  - Slow query detection (logs warnings for requests > 1s)

Usage — add to main.py:
    from src.api.monitoring import setup_monitoring
    setup_monitoring(app)

Then access:
    GET /metrics   — Prometheus metrics
    GET /stats     — JSON stats dashboard
"""

import time
import json
import logging
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Callable

# ─── Structured Logger ────────────────────────────────────────────────────

def get_logger(name: str) -> logging.Logger:
    """Return a logger that emits structured JSON lines."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


class StructuredFormatter(logging.Formatter):
    """Formats log records as single-line JSON for log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
        }
        # Merge any extra fields passed via extra={}
        for key, val in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "levelname", "levelno",
                "pathname", "filename", "module", "exc_info",
                "exc_text", "stack_info", "lineno", "funcName",
                "created", "msecs", "relativeCreated", "thread",
                "threadName", "processName", "process", "message",
            ):
                log_entry[key] = val

        return json.dumps(log_entry, default=str)


logger = get_logger("trade_confirmation")


# ─── In-Memory Metrics Store ──────────────────────────────────────────────

class MetricsStore:
    """
    Thread-safe in-memory metrics store.

    Tracks:
      - request_count      per endpoint + method
      - error_count        per endpoint (4xx/5xx)
      - latency_samples    per endpoint (rolling 1000 samples)
      - slow_queries       list of queries taking > SLOW_THRESHOLD_MS
      - search_queries     recent search queries (for analytics)
    """

    SLOW_THRESHOLD_MS = 1000    # Log warning for requests > 1s
    MAX_SAMPLES       = 1000    # Max latency samples per endpoint
    MAX_SLOW_QUERIES  = 100
    MAX_RECENT_QUERIES = 50

    def __init__(self):
        self._lock = threading.Lock()
        self._request_count:  dict[str, int]         = defaultdict(int)
        self._error_count:    dict[str, int]         = defaultdict(int)
        self._latency:        dict[str, deque]       = defaultdict(
            lambda: deque(maxlen=self.MAX_SAMPLES)
        )
        self._slow_queries:   deque                  = deque(maxlen=self.MAX_SLOW_QUERIES)
        self._recent_searches: deque                 = deque(maxlen=self.MAX_RECENT_QUERIES)
        self._start_time = time.time()

    def record_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        query: str = "",
    ):
        key = f"{method} {path}"
        with self._lock:
            self._request_count[key] += 1
            self._latency[key].append(duration_ms)

            if status_code >= 400:
                self._error_count[key] += 1

            if duration_ms > self.SLOW_THRESHOLD_MS:
                self._slow_queries.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "endpoint":  key,
                    "duration_ms": round(duration_ms, 1),
                    "status_code": status_code,
                })
                logger.warning(
                    f"Slow request detected",
                    extra={
                        "endpoint": key,
                        "duration_ms": round(duration_ms, 1),
                        "status_code": status_code,
                    }
                )

            if path == "/search" and query:
                self._recent_searches.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "query": query[:100],
                    "duration_ms": round(duration_ms, 1),
                    "status_code": status_code,
                })

    def get_stats(self) -> dict:
        """Return a JSON-serialisable stats summary."""
        with self._lock:
            uptime = round(time.time() - self._start_time, 0)
            total_requests = sum(self._request_count.values())
            total_errors   = sum(self._error_count.values())

            endpoint_stats = {}
            for key in self._request_count:
                samples = list(self._latency[key])
                sorted_s = sorted(samples)
                n = len(sorted_s)
                endpoint_stats[key] = {
                    "requests": self._request_count[key],
                    "errors":   self._error_count.get(key, 0),
                    "p50_ms":   round(sorted_s[n // 2], 1)         if n else 0,
                    "p95_ms":   round(sorted_s[int(n * 0.95)], 1)  if n else 0,
                    "p99_ms":   round(sorted_s[int(n * 0.99)], 1)  if n else 0,
                    "mean_ms":  round(sum(sorted_s) / n, 1)         if n else 0,
                }

            return {
                "uptime_seconds":    uptime,
                "total_requests":    total_requests,
                "total_errors":      total_errors,
                "error_rate_pct":    round(total_errors / max(total_requests, 1) * 100, 2),
                "endpoints":         endpoint_stats,
                "slow_queries":      list(self._slow_queries)[-10:],
                "recent_searches":   list(self._recent_searches)[-10:],
                "timestamp":         datetime.now(timezone.utc).isoformat(),
            }

    def prometheus_format(self) -> str:
        """Render metrics in Prometheus text exposition format."""
        lines = []
        with self._lock:
            for key, count in self._request_count.items():
                safe_key = key.replace(" ", "_").replace("/", "_").strip("_")
                lines.append(f'# HELP http_requests_total Total HTTP requests')
                lines.append(f'# TYPE http_requests_total counter')
                lines.append(f'http_requests_total{{endpoint="{key}"}} {count}')

                errors = self._error_count.get(key, 0)
                lines.append(f'http_errors_total{{endpoint="{key}"}} {errors}')

                samples = list(self._latency[key])
                if samples:
                    sorted_s = sorted(samples)
                    n = len(sorted_s)
                    lines.append(f'http_latency_p50_ms{{endpoint="{key}"}} {round(sorted_s[n//2], 1)}')
                    lines.append(f'http_latency_p95_ms{{endpoint="{key}"}} {round(sorted_s[int(n*0.95)], 1)}')

        lines.append(f'api_uptime_seconds {round(time.time() - self._start_time, 0)}')
        return "\n".join(lines) + "\n"


# Singleton metrics store
metrics = MetricsStore()


# ─── FastAPI Integration ──────────────────────────────────────────────────

def setup_monitoring(app):
    """
    Attach monitoring middleware and /metrics + /stats endpoints to a FastAPI app.

    Usage in main.py:
        from src.api.monitoring import setup_monitoring
        setup_monitoring(app)
    """
    from fastapi import Request
    from fastapi.responses import PlainTextResponse, JSONResponse

    @app.middleware("http")
    async def monitoring_middleware(request: Request, call_next: Callable):
        start = time.perf_counter()

        # Extract search query for analytics
        query = ""
        if request.url.path == "/search" and request.method == "POST":
            try:
                body = await request.body()
                body_json = json.loads(body)
                query = body_json.get("query", "")
                # Re-inject body so the route handler can read it
                from starlette.datastructures import Headers
                async def receive():
                    return {"type": "http.request", "body": body}
                request._receive = receive
            except Exception:
                pass

        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        # Skip logging for static/docs endpoints
        skip_paths = {"/docs", "/redoc", "/openapi.json", "/favicon.ico"}
        if request.url.path not in skip_paths:
            metrics.record_request(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                query=query,
            )
            logger.info(
                f"{request.method} {request.url.path} {response.status_code}",
                extra={
                    "method":       request.method,
                    "path":         request.url.path,
                    "status_code":  response.status_code,
                    "duration_ms":  round(duration_ms, 1),
                    "client_ip":    request.client.host if request.client else "unknown",
                }
            )

        return response

    @app.get("/metrics", tags=["System"],
             summary="Prometheus-compatible metrics",
             response_class=PlainTextResponse)
    async def prometheus_metrics():
        return PlainTextResponse(
            content=metrics.prometheus_format(),
            media_type="text/plain; version=0.0.4"
        )

    @app.get("/stats", tags=["System"],
             summary="JSON stats dashboard")
    async def stats_dashboard():
        return JSONResponse(content=metrics.get_stats())

    logger.info("Monitoring middleware and /metrics + /stats endpoints registered")
    return app
