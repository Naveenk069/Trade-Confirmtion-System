"""
search_engine.py — Semantic search interface for trade confirmation templates.

Takes a natural-language or structured query, embeds it, and returns ranked
templates from the vector store with optional metadata filters.

Usage:
    engine = SearchEngine.from_pipeline(pipeline)

    # Natural language query
    results = engine.search("Goldman Sachs interest rate swap USD 5 year")

    # Structured query with filters
    results = engine.search(
        "fixed floating SOFR",
        filters={"trade_type": "Interest Rate Swap", "jurisdiction": "US"}
    )
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DEFAULT_TOP_K
from src.embedder import BaseEmbedder
from src.vector_store import VectorStore, SearchResult


# ─── Search Engine ────────────────────────────────────────────────────────

class SearchEngine:
    """
    Semantic search over the trade confirmation template corpus.

    Wraps the embedder + vector store into a clean search interface.
    """

    def __init__(self, embedder: BaseEmbedder, store: VectorStore):
        self._embedder = embedder
        self._store = store

    @classmethod
    def from_pipeline(cls, pipeline) -> "SearchEngine":
        """Convenience constructor: build a SearchEngine from an IngestionPipeline."""
        return cls(embedder=pipeline.embedder, store=pipeline.store)

    # ── Core search ──────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        filters: Optional[dict] = None,
        active_only: bool = True,
    ) -> list[SearchResult]:
        """
        Search for templates matching the query.

        Args:
            query:       Natural language or keyword query string.
                         e.g. "Goldman Sachs interest rate swap USD"
            top_k:       Maximum number of results to return.
            filters:     Metadata filters. All conditions must match (AND).
                         e.g. {"trade_type": "Interest Rate Swap", "jurisdiction": "US"}
            active_only: If True, only return templates with status="active".

        Returns:
            Ranked list of SearchResult objects (highest score first).
        """
        if not query.strip():
            raise ValueError("Search query cannot be empty.")

        # Build effective filters
        effective_filters = dict(filters or {})
        if active_only:
            effective_filters["status"] = "active"

        # Embed the query
        query_vector = self._embedder.embed(query)

        # Search
        results = self._store.search(
            query_vector=query_vector,
            top_k=top_k,
            filters=effective_filters if effective_filters else None,
        )

        return results

    def search_by_trade(
        self,
        trade_type: str,
        counterparty: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[SearchResult]:
        """
        Structured search by known trade attributes.

        This is a convenience method for the most common use case:
        an ops user selecting from dropdowns in the UI.

        Args:
            trade_type:   e.g. "Interest Rate Swap"
            counterparty: e.g. "Goldman Sachs" (optional)
            jurisdiction: e.g. "US" (optional)
            top_k:        Max results.

        Returns:
            Ranked list of matching templates.
        """
        # Build query string from known attributes
        query_parts = [trade_type]
        if counterparty:
            query_parts.append(counterparty)
        if jurisdiction:
            query_parts.append(jurisdiction)

        query = " ".join(query_parts)

        filters: dict = {"trade_type": trade_type}
        if counterparty:
            filters["counterparty"] = counterparty
        if jurisdiction:
            filters["jurisdiction"] = jurisdiction

        return self.search(query=query, top_k=top_k, filters=filters)

    def get_all_templates(self, active_only: bool = True) -> list[dict]:
        """
        Return all templates in the repository (no search, no ranking).
        Used to populate the template browser in the UI.
        """
        all_docs = self._store.list_all()
        if active_only:
            return [d for d in all_docs if d.get("status", "active") == "active"]
        return all_docs

    # ── Facets ───────────────────────────────────────────────────────────

    def get_facets(self) -> dict:
        """
        Return unique values for each filterable metadata field.
        Used to populate filter dropdowns in the UI.

        Returns:
            {
              "trade_types":   ["Credit Default Swap", "FX Forward", ...],
              "counterparties": ["Barclays", "Goldman Sachs", ...],
              "jurisdictions": ["EU", "UK", "US"],
              "products":      ["CDS", "FX", "IRS", ...]
            }
        """
        all_docs = self._store.list_all()
        return {
            "trade_types":    sorted({d.get("trade_type", "")    for d in all_docs if d.get("trade_type")}),
            "counterparties": sorted({d.get("counterparty", "")  for d in all_docs if d.get("counterparty")}),
            "jurisdictions":  sorted({d.get("jurisdiction", "")  for d in all_docs if d.get("jurisdiction")}),
            "products":       sorted({d.get("product", "")       for d in all_docs if d.get("product")}),
        }

    # ── Display helpers ───────────────────────────────────────────────────

    def print_results(self, results: list[SearchResult], query: str = "") -> None:
        """Pretty-print search results to the terminal."""
        if query:
            print(f"\n  🔍 Query: \"{query}\"")
        print(f"  📋 {len(results)} result(s) found\n")

        if not results:
            print("  No matching templates found.")
            return

        for i, r in enumerate(results, 1):
            bar = "█" * int(r.score * 20) + "░" * (20 - int(r.score * 20))
            print(f"  [{i}] {r.filename}")
            print(f"       Score:       {r.score:.3f}  {bar}")
            print(f"       Trade Type:  {r.metadata.get('trade_type', 'N/A')}")
            print(f"       Counterparty:{r.metadata.get('counterparty', 'N/A')}")
            print(f"       Jurisdiction:{r.metadata.get('jurisdiction', 'N/A')}")
            print(f"       Product:     {r.metadata.get('product', 'N/A')}")
            print(f"       Version:     {r.metadata.get('version', 'N/A')}")
            if r.snippet:
                snippet = r.snippet[:120].replace("\n", " ")
                print(f"       Snippet:     {snippet}...")
            print()


if __name__ == "__main__":
    from src.ingestion_pipeline import IngestionPipeline
    from src.template_generator import generate_all_templates
    from src.config import TEMPLATES_DIR

    # Generate + ingest templates
    print("\n📄 Generating templates...")
    generate_all_templates()

    pipeline = IngestionPipeline()
    pipeline.run(force=True)

    # Build search engine
    engine = SearchEngine.from_pipeline(pipeline)

    # Run example searches
    test_queries = [
        ("interest rate swap Goldman Sachs USD",        {}),
        ("FX forward JPY settlement SWIFT",              {}),
        ("credit default swap protection buyer seller",  {}),
        ("SOFR floating rate quarterly payment",
            {"trade_type": "Interest Rate Swap"}),
        ("IRS UK jurisdiction",
            {"jurisdiction": "UK"}),
    ]

    print("\n" + "=" * 60)
    print("  SEARCH ENGINE DEMO")
    print("=" * 60)

    for query, filters in test_queries:
        results = engine.search(query, filters=filters if filters else None)
        engine.print_results(results, query=query + (f" [filter: {filters}]" if filters else ""))

    # Show facets
    print("\n  📊 Repository Facets:")
    facets = engine.get_facets()
    for facet_name, values in facets.items():
        print(f"    {facet_name}: {values}")
