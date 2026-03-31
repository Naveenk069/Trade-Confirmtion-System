"""
config.py — Central configuration for the Trade Confirmation System.
All tuneable parameters live here. No magic numbers elsewhere.
"""

from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).resolve().parent.parent
TEMPLATES_DIR   = BASE_DIR / "templates"
DATA_DIR        = BASE_DIR / "data"
VECTOR_STORE_DIR = DATA_DIR / "vector_store"

# Ensure directories exist at import time
for _dir in [TEMPLATES_DIR, DATA_DIR, VECTOR_STORE_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# ─── Embedding Backend ────────────────────────────────────────────────────
# Options:
#   "tfidf"                  — numpy TF-IDF (no GPU, no install, works offline)
#   "sentence-transformers"  — all-MiniLM-L6-v2 (recommended for production)
#   "openai"                 — text-embedding-3-small (requires OPENAI_API_KEY)
EMBEDDING_BACKEND = "tfidf"

# Only used when EMBEDDING_BACKEND == "sentence-transformers"
SENTENCE_TRANSFORMER_MODEL = "all-MiniLM-L6-v2"

# Only used when EMBEDDING_BACKEND == "openai"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"

# ─── Vector Store ─────────────────────────────────────────────────────────
# Options: "chroma" (production), "json" (dev/offline fallback)
VECTOR_STORE_BACKEND = "json"
CHROMA_COLLECTION_NAME = "trade_confirmations"

# ─── Search ───────────────────────────────────────────────────────────────
DEFAULT_TOP_K = 5               # Number of results to return by default
MIN_SIMILARITY_SCORE = 0.10     # Minimum cosine similarity to include in results

# ─── Document Parsing ─────────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = [".docx", ".pdf", ".txt"]

# Metadata fields extracted / required for every template
REQUIRED_METADATA_FIELDS = [
    "trade_type",       # e.g. "Interest Rate Swap", "FX Forward"
    "counterparty",     # e.g. "Goldman Sachs", "JP Morgan"
    "jurisdiction",     # e.g. "US", "UK", "EU"
    "product",          # e.g. "IRS", "FX", "CDS", "Equity Swap"
    "version",          # e.g. "1.0"
    "status",           # "active" | "draft" | "deprecated"
]

# ─── Logging ──────────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"
