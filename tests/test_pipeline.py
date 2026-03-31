"""
test_pipeline.py — Unit and integration tests for all pipeline components.

Run with:  python -m pytest tests/ -v
Or:        python tests/test_pipeline.py
"""

import sys
import math
import tempfile
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ─── Unit Tests: Document Parser ─────────────────────────────────────────

def test_document_parser_extracts_metadata():
    """Parser should extract trade type, counterparty, and jurisdiction from a .docx."""
    from src.document_parser import DocumentParser
    from src.template_generator import generate_template, TEMPLATES
    from src.config import TEMPLATES_DIR

    template_def = TEMPLATES[0]  # IRS Goldman Sachs
    path = generate_template(template_def, TEMPLATES_DIR)

    parser = DocumentParser()
    doc = parser.parse(path)

    assert doc.trade_type == "Interest Rate Swap", f"Got: {doc.trade_type}"
    assert "Goldman" in doc.counterparty, f"Got: {doc.counterparty}"
    assert doc.jurisdiction == "US", f"Got: {doc.jurisdiction}"
    assert doc.product == "IRS", f"Got: {doc.product}"
    assert len(doc.full_text) > 100, "Full text should be substantial"
    print(f"  ✅ Parser test passed: {doc.filename}")


def test_document_parser_handles_missing_file():
    """Parser should raise FileNotFoundError for missing files."""
    from src.document_parser import DocumentParser
    parser = DocumentParser()
    try:
        parser.parse(Path("/nonexistent/file.docx"))
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        print("  ✅ Parser correctly raises FileNotFoundError")


def test_document_parser_parses_directory():
    """Parser should parse all templates in a directory."""
    from src.document_parser import DocumentParser
    from src.template_generator import generate_all_templates
    from src.config import TEMPLATES_DIR

    generate_all_templates()
    parser = DocumentParser()
    docs = parser.parse_directory(TEMPLATES_DIR)

    assert len(docs) >= 8, f"Expected >= 8 templates, got {len(docs)}"
    for doc in docs:
        assert doc.filename.endswith(".docx"), f"Unexpected extension: {doc.filename}"
        assert doc.full_text, f"Empty text for {doc.filename}"
    print(f"  ✅ Directory parser test passed: {len(docs)} documents")


# ─── Unit Tests: Embedder ─────────────────────────────────────────────────

def test_tfidf_embedder_produces_vectors():
    """TF-IDF embedder should produce unit-norm vectors."""
    from src.embedder import TFIDFEmbedder

    embedder = TFIDFEmbedder()
    corpus = [
        "Interest Rate Swap SOFR Goldman Sachs USD notional fixed rate",
        "FX Forward EUR USD JPY settlement SWIFT counterparty",
        "Credit Default Swap protection buyer seller reference entity",
    ]
    embedder.fit(corpus)
    vecs = embedder.embed_batch(corpus)

    assert len(vecs) == 3
    for i, vec in enumerate(vecs):
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 1e-6, f"Vector {i} not unit-norm: {norm}"
    print(f"  ✅ Embedder produces unit-norm vectors (dim={embedder.dimension})")


def test_tfidf_embedder_similarity_ranking():
    """Similar documents should score higher than dissimilar ones."""
    from src.embedder import TFIDFEmbedder

    embedder = TFIDFEmbedder()
    corpus = [
        "interest rate swap SOFR Goldman Sachs USD fixed floating notional",
        "FX forward foreign exchange EUR USD SWIFT settlement delivery",
        "credit default swap CDS protection buyer seller reference entity bankruptcy",
    ]
    embedder.fit(corpus)
    vecs = embedder.embed_batch(corpus)

    # Query similar to doc 0 (IRS)
    query_vec = embedder.embed("interest rate swap SOFR fixed floating")
    sims = [embedder.similarity(query_vec, v) for v in vecs]

    assert sims[0] > sims[1], f"IRS doc should rank above FX doc: {sims}"
    assert sims[0] > sims[2], f"IRS doc should rank above CDS doc: {sims}"
    print(f"  ✅ Similarity ranking correct: IRS={sims[0]:.3f}, FX={sims[1]:.3f}, CDS={sims[2]:.3f}")


def test_get_embedder_factory():
    """get_embedder() should return the correct backend."""
    from src.embedder import get_embedder, TFIDFEmbedder

    embedder = get_embedder("tfidf")
    assert isinstance(embedder, TFIDFEmbedder)
    print("  ✅ Embedder factory returns correct backend")


# ─── Unit Tests: Vector Store ─────────────────────────────────────────────

def test_json_vector_store_add_and_search():
    """JSONVectorStore should store vectors and retrieve them by similarity."""
    from src.vector_store import JSONVectorStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = JSONVectorStore(store_path=Path(tmpdir) / "test.json")

        # Add 3 documents with known vectors
        doc_vecs = {
            "doc_irs": [1.0, 0.0, 0.0],
            "doc_fx":  [0.0, 1.0, 0.0],
            "doc_cds": [0.0, 0.0, 1.0],
        }

        for doc_id, vec in doc_vecs.items():
            store.add(
                doc_id=doc_id,
                vector=vec,
                metadata={"filename": f"{doc_id}.docx", "trade_type": doc_id, "status": "active"},
                text=f"Sample text for {doc_id}",
            )

        assert store.count() == 3

        # Query closest to doc_irs
        results = store.search(query_vector=[0.9, 0.1, 0.0], top_k=3)
        assert len(results) > 0
        assert results[0].doc_id == "doc_irs", f"Top result should be doc_irs, got {results[0].doc_id}"
        print(f"  ✅ Vector store search returns correct top result: {results[0].doc_id}")


def test_json_vector_store_metadata_filtering():
    """Metadata filters should restrict results correctly."""
    from src.vector_store import JSONVectorStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = JSONVectorStore(store_path=Path(tmpdir) / "test.json")

        store.add("doc1", [1.0, 0.0], {"filename": "a.docx", "trade_type": "IRS", "status": "active", "jurisdiction": "US"}, "text")
        store.add("doc2", [0.9, 0.1], {"filename": "b.docx", "trade_type": "IRS", "status": "active", "jurisdiction": "UK"}, "text")
        store.add("doc3", [0.8, 0.2], {"filename": "c.docx", "trade_type": "FX",  "status": "active", "jurisdiction": "US"}, "text")

        # Filter by jurisdiction=US only
        results = store.search([1.0, 0.0], top_k=5, filters={"jurisdiction": "US"})
        filenames = [r.filename for r in results]
        assert "b.docx" not in filenames, "UK doc should be filtered out"
        assert "a.docx" in filenames or "c.docx" in filenames
        print(f"  ✅ Metadata filtering works: {filenames}")


def test_json_vector_store_delete():
    """Deleted documents should not appear in search results."""
    from src.vector_store import JSONVectorStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = JSONVectorStore(store_path=Path(tmpdir) / "test.json")
        store.add("doc1", [1.0, 0.0], {"filename": "a.docx", "trade_type": "IRS", "status": "active"}, "text")
        store.add("doc2", [0.9, 0.1], {"filename": "b.docx", "trade_type": "FX",  "status": "active"}, "text")

        assert store.count() == 2
        deleted = store.delete("doc1")
        assert deleted is True
        assert store.count() == 1
        print("  ✅ Vector store delete works correctly")


# ─── Integration Tests: Full Pipeline ─────────────────────────────────────

def test_full_pipeline_end_to_end():
    """
    Full integration test:
    generate templates → ingest → search → verify results
    """
    import tempfile
    from src.template_generator import generate_all_templates
    from src.ingestion_pipeline import IngestionPipeline
    from src.search_engine import SearchEngine
    from src.config import TEMPLATES_DIR

    # Generate sample templates
    generate_all_templates()

    # Run ingestion
    pipeline = IngestionPipeline(
        embedding_backend="tfidf",
        vector_store_backend="json",
    )
    report = pipeline.run(force=True)

    assert report.ingested >= 8, f"Expected >= 8 ingested, got {report.ingested}"
    assert report.failed == 0, f"Pipeline had failures: {report.records}"
    print(f"  ✅ Pipeline ingested {report.ingested} templates with 0 failures")

    # Search
    engine = SearchEngine.from_pipeline(pipeline)

    # Test 1: IRS query should return IRS templates at top
    results = engine.search("interest rate swap SOFR USD Goldman Sachs fixed floating")
    assert len(results) > 0, "Should return at least 1 result"
    top_trade_types = [r.metadata.get("trade_type") for r in results[:3]]
    assert "Interest Rate Swap" in top_trade_types, f"IRS should appear in top 3: {top_trade_types}"
    print(f"  ✅ IRS query returns IRS in top results: {top_trade_types}")

    # Test 2: FX query should return FX templates at top
    results = engine.search("foreign exchange forward EUR JPY SWIFT settlement")
    top_trade_types = [r.metadata.get("trade_type") for r in results[:3]]
    assert "FX Forward" in top_trade_types, f"FX Forward should appear in top 3: {top_trade_types}"
    print(f"  ✅ FX query returns FX Forward in top results: {top_trade_types}")

    # Test 3: Filtered search
    results = engine.search("interest rate swap", filters={"jurisdiction": "UK"})
    jurisdictions = [r.metadata.get("jurisdiction") for r in results]
    assert all(j == "UK" for j in jurisdictions), f"Filter should only return UK: {jurisdictions}"
    print(f"  ✅ Filtered search (jurisdiction=UK) returns only UK templates")

    # Test 4: Facets
    facets = engine.get_facets()
    assert "trade_types" in facets
    assert "Interest Rate Swap" in facets["trade_types"]
    assert "FX Forward" in facets["trade_types"]
    print(f"  ✅ Facets: {facets['trade_types']}")


def test_pipeline_idempotent():
    """Running the pipeline twice should not duplicate entries."""
    from src.template_generator import generate_all_templates
    from src.ingestion_pipeline import IngestionPipeline
    from src.config import TEMPLATES_DIR

    generate_all_templates()
    pipeline = IngestionPipeline()

    pipeline.run(force=True)
    count_after_first = pipeline.store.count()

    report2 = pipeline.run(force=False)  # Should skip all
    count_after_second = pipeline.store.count()

    assert count_after_first == count_after_second, (
        f"Store grew on second run: {count_after_first} → {count_after_second}"
    )
    assert report2.skipped == count_after_first
    print(f"  ✅ Pipeline is idempotent: {count_after_first} docs, 0 duplicates")


# ─── Test Runner ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        # Unit tests
        test_document_parser_extracts_metadata,
        test_document_parser_handles_missing_file,
        test_document_parser_parses_directory,
        test_tfidf_embedder_produces_vectors,
        test_tfidf_embedder_similarity_ranking,
        test_get_embedder_factory,
        test_json_vector_store_add_and_search,
        test_json_vector_store_metadata_filtering,
        test_json_vector_store_delete,
        # Integration tests
        test_full_pipeline_end_to_end,
        test_pipeline_idempotent,
    ]

    print("\n" + "="*60)
    print("  RUNNING TEST SUITE")
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
            failed += 1
        print()

    print("="*60)
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("="*60 + "\n")

    if failed > 0:
        sys.exit(1)
