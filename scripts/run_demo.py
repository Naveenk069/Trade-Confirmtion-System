"""
run_demo.py — Full end-to-end demo of the Iteration 1 pipeline.

Runs:
  1. Generate 8 dummy trade confirmation templates (.docx)
  2. Parse all templates (extract text + metadata)
  3. Embed templates (TF-IDF)
  4. Store in JSON vector store
  5. Run 6 example searches with results display
  6. Show repository facets
  7. Run test suite
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.template_generator import generate_all_templates
from src.ingestion_pipeline import IngestionPipeline
from src.search_engine import SearchEngine
from src.config import TEMPLATES_DIR


def divider(title: str = "") -> None:
    if title:
        print(f"\n{'─'*60}")
        print(f"  {title}")
        print(f"{'─'*60}")
    else:
        print(f"\n{'─'*60}")


def main():
    print("\n" + "="*60)
    print("  AI/ML Trade Confirmation Automation")
    print("  Iteration 1: Intelligent Template Reuse — DEMO")
    print("="*60)

    # ── Step 1: Generate dummy templates ─────────────────────────────────
    divider("STEP 1 — Generating sample templates")
    templates = generate_all_templates()
    print(f"\n  ✅ {len(templates)} templates ready in: {TEMPLATES_DIR}")

    # ── Step 2-4: Run the ingestion pipeline ──────────────────────────────
    divider("STEP 2 — Running ingestion pipeline (parse → embed → store)")
    pipeline = IngestionPipeline(
        embedding_backend="tfidf",
        vector_store_backend="json",
    )
    report = pipeline.run(force=True)

    # ── Step 5: Search demos ──────────────────────────────────────────────
    engine = SearchEngine.from_pipeline(pipeline)

    divider("STEP 3 — Semantic Search Demos")

    searches = [
        {
            "label": "Query 1 — Find IRS templates for Goldman Sachs",
            "query": "Goldman Sachs interest rate swap USD fixed rate SOFR",
            "filters": None,
        },
        {
            "label": "Query 2 — Find any FX Forward template",
            "query": "foreign exchange forward settlement SWIFT",
            "filters": None,
        },
        {
            "label": "Query 3 — Credit Default Swap with protection seller",
            "query": "credit default swap CDS protection seller reference entity",
            "filters": None,
        },
        {
            "label": "Query 4 — IRS templates filtered to UK jurisdiction only",
            "query": "interest rate swap floating SONIA",
            "filters": {"jurisdiction": "UK"},
        },
        {
            "label": "Query 5 — Any active template with SOFR (no filters)",
            "query": "SOFR compounded arrears lookback variation margin",
            "filters": None,
        },
        {
            "label": "Query 6 — Structured search: IRS + Goldman Sachs",
            "query": None,  # uses search_by_trade()
            "trade_type": "Interest Rate Swap",
            "counterparty": "Goldman Sachs",
        },
    ]

    for s in searches:
        divider(s["label"])

        if s.get("query") is None:
            # Structured search
            results = engine.search_by_trade(
                trade_type=s["trade_type"],
                counterparty=s.get("counterparty"),
                top_k=3,
            )
            engine.print_results(results, query=f"[structured] {s['trade_type']} / {s.get('counterparty', 'any')}")
        else:
            results = engine.search(
                s["query"],
                top_k=3,
                filters=s.get("filters"),
            )
            label = s["query"]
            if s.get("filters"):
                label += f"  [filter: {s['filters']}]"
            engine.print_results(results, query=label)

    # ── Step 6: Repository facets ────────────────────────────────────────
    divider("STEP 4 — Repository Facets (for UI dropdowns)")
    facets = engine.get_facets()
    for name, values in facets.items():
        print(f"\n  {name}:")
        for v in values:
            print(f"    • {v}")

    # ── Step 7: Run test suite ────────────────────────────────────────────
    divider("STEP 5 — Running Test Suite")
    import subprocess
    result = subprocess.run(
        [sys.executable, "tests/test_pipeline.py"],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=False,
    )

    # ── Final summary ─────────────────────────────────────────────────────
    divider()
    print("\n  🎉 DEMO COMPLETE\n")
    print("  What was built (Iteration 1, Phase 0–1):")
    print("    ✅ 8 realistic trade confirmation templates (.docx)")
    print("    ✅ Document parser (extracts text + metadata from .docx)")
    print("    ✅ TF-IDF embedder (swap to sentence-transformers in config.py)")
    print("    ✅ JSON vector store (swap to ChromaDB in config.py)")
    print("    ✅ Ingestion pipeline (idempotent, resumable)")
    print("    ✅ Semantic search engine with metadata filtering")
    print("    ✅ Full test suite (unit + integration)")
    print()
    print("  Next steps (Iteration 1, Phase 2):")
    print("    → Build FastAPI REST endpoints (/search, /templates, /ingest)")
    print("    → Swap embedder to sentence-transformers for production")
    print("    → Swap vector store to ChromaDB for persistence")
    print("    → Build Streamlit UI (Phase 3)")
    print()


if __name__ == "__main__":
    main()
