"""
ingestion_pipeline.py — Orchestrates the full template ingestion workflow.

Pipeline stages:
  1. DISCOVER  — find all template files in a directory
  2. PARSE     — extract text + metadata from each file
  3. EMBED     — generate embedding vectors
  4. STORE     — save vectors + metadata to the vector store
  5. REPORT    — print a summary of what was ingested

Design goals:
  - Idempotent: re-running won't duplicate entries (upsert by filename)
  - Resumable: already-ingested files are skipped unless force=True
  - Observable: prints progress at every stage
"""

import sys
import uuid
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import TEMPLATES_DIR, EMBEDDING_BACKEND, VECTOR_STORE_BACKEND
from src.document_parser import DocumentParser, ParsedDocument
from src.embedder import get_embedder, TFIDFEmbedder
from src.vector_store import get_vector_store, VectorStore


# ─── Result Models ────────────────────────────────────────────────────────

@dataclass
class IngestionRecord:
    """Result of ingesting a single document."""
    filename: str
    doc_id: str
    success: bool
    skipped: bool = False
    error: Optional[str] = None
    trade_type: str = ""
    counterparty: str = ""


@dataclass
class IngestionReport:
    """Summary of a full pipeline run."""
    total_files: int = 0
    ingested: int = 0
    skipped: int = 0
    failed: int = 0
    duration_seconds: float = 0.0
    records: list[IngestionRecord] = field(default_factory=list)

    def print_summary(self) -> None:
        print("\n" + "=" * 60)
        print("  INGESTION PIPELINE REPORT")
        print("=" * 60)
        print(f"  Total files found : {self.total_files}")
        print(f"  ✅ Ingested        : {self.ingested}")
        print(f"  ⏭  Skipped         : {self.skipped}")
        print(f"  ❌ Failed          : {self.failed}")
        print(f"  ⏱  Duration        : {self.duration_seconds:.2f}s")
        print("=" * 60)

        if self.failed > 0:
            print("\n  Failed files:")
            for r in self.records:
                if not r.success and not r.skipped:
                    print(f"    • {r.filename}: {r.error}")

        print()


# ─── Pipeline ─────────────────────────────────────────────────────────────

class IngestionPipeline:
    """
    End-to-end template ingestion pipeline.

    Usage:
        pipeline = IngestionPipeline()
        report = pipeline.run(templates_dir=Path("templates/"))

    Or ingest a single file:
        pipeline.ingest_file(Path("templates/IRS_Goldman.docx"))
    """

    def __init__(
        self,
        embedding_backend: str = EMBEDDING_BACKEND,
        vector_store_backend: str = VECTOR_STORE_BACKEND,
    ):
        self._parser = DocumentParser()
        self._embedder = get_embedder(embedding_backend)
        self._store = get_vector_store(vector_store_backend)
        self._embedding_backend = embedding_backend

    # ── Public API ───────────────────────────────────────────────────────

    def run(
        self,
        templates_dir: Path = TEMPLATES_DIR,
        force: bool = False,
    ) -> IngestionReport:
        """
        Run the full ingestion pipeline on a directory of templates.

        Args:
            templates_dir: Directory containing .docx / .pdf / .txt files.
            force:         If True, re-ingest files already in the store.

        Returns:
            IngestionReport with counts and per-file results.
        """
        templates_dir = Path(templates_dir)
        report = IngestionReport()
        start_time = time.time()

        print(f"\n{'='*60}")
        print(f"  INGESTION PIPELINE STARTING")
        print(f"  Directory: {templates_dir}")
        print(f"  Embedder:  {self._embedder.backend_name}")
        print(f"{'='*60}\n")

        # Stage 1: Discover files
        print("  Stage 1/4 — Discovering templates...")
        docs = self._parser.parse_directory(templates_dir)
        report.total_files = len(docs)

        if not docs:
            print("  ⚠ No supported documents found. Exiting.\n")
            return report

        print(f"  Found {len(docs)} document(s)\n")

        # Stage 2: Filter already-ingested (unless force=True)
        existing = {d["filename"] for d in self._store.list_all()}
        to_ingest = []
        for doc in docs:
            if not force and doc.filename in existing:
                report.skipped += 1
                report.records.append(IngestionRecord(
                    filename=doc.filename, doc_id="", success=True, skipped=True
                ))
                print(f"  ⏭  Skipping (already ingested): {doc.filename}")
            else:
                to_ingest.append(doc)

        if not to_ingest:
            print("\n  All files already ingested. Use force=True to re-ingest.\n")
            report.duration_seconds = time.time() - start_time
            return report

        # Stage 3: Fit embedder on corpus (TF-IDF needs this; others ignore it)
        print(f"\n  Stage 2/4 — Generating embeddings ({self._embedding_backend})...")
        texts = [doc.full_text for doc in to_ingest]

        if isinstance(self._embedder, TFIDFEmbedder):
            # TF-IDF: fit on all texts at once for a consistent vocabulary
            self._embedder.fit(texts)
            vectors = self._embedder.embed_batch(texts)
        else:
            # sentence-transformers / OpenAI: batch encode
            vectors = self._embedder.embed_batch(texts)

        print(f"  Embedding dimension: {self._embedder.dimension}")

        # Stage 4: Store
        print(f"\n  Stage 3/4 — Storing in vector store...")
        for doc, vector in zip(to_ingest, vectors):
            try:
                doc_id = self._make_id(doc.filename)
                self._store.add(
                    doc_id=doc_id,
                    vector=vector,
                    metadata=doc.metadata_dict,
                    text=doc.full_text,
                )
                record = IngestionRecord(
                    filename=doc.filename,
                    doc_id=doc_id,
                    success=True,
                    trade_type=doc.trade_type,
                    counterparty=doc.counterparty,
                )
                report.ingested += 1
                print(f"  ✅ Stored: {doc.filename} [{doc.trade_type} / {doc.counterparty}]")
            except Exception as e:
                record = IngestionRecord(
                    filename=doc.filename,
                    doc_id="",
                    success=False,
                    error=str(e),
                )
                report.failed += 1
                print(f"  ❌ Failed: {doc.filename}: {e}")

            report.records.append(record)

        # Stage 5: Report
        print(f"\n  Stage 4/4 — Verifying store...")
        total_in_store = self._store.count()
        print(f"  Total documents in store: {total_in_store}")

        report.duration_seconds = time.time() - start_time
        report.print_summary()
        return report

    def ingest_file(self, file_path: Path, force: bool = False) -> IngestionRecord:
        """
        Ingest a single file. Useful for adding individual new templates.

        Args:
            file_path: Path to the template file.
            force:     Re-ingest even if already stored.

        Returns:
            IngestionRecord with the result.
        """
        file_path = Path(file_path)

        # Check if already exists
        existing = {d["filename"]: d for d in self._store.list_all()}
        if not force and file_path.name in existing:
            print(f"  ⏭  Skipping (already ingested): {file_path.name}")
            return IngestionRecord(
                filename=file_path.name, doc_id="", success=True, skipped=True
            )

        try:
            doc = self._parser.parse(file_path)
        except Exception as e:
            return IngestionRecord(
                filename=file_path.name, doc_id="", success=False, error=str(e)
            )

        try:
            vector = self._embedder.embed(doc.full_text)
        except Exception as e:
            return IngestionRecord(
                filename=file_path.name, doc_id="", success=False,
                error=f"Embedding failed: {e}"
            )

        try:
            doc_id = self._make_id(doc.filename)
            self._store.add(
                doc_id=doc_id,
                vector=vector,
                metadata=doc.metadata_dict,
                text=doc.full_text,
            )
        except Exception as e:
            return IngestionRecord(
                filename=file_path.name, doc_id="", success=False,
                error=f"Store failed: {e}"
            )

        print(f"  ✅ Ingested: {file_path.name}")
        return IngestionRecord(
            filename=file_path.name,
            doc_id=doc_id,
            success=True,
            trade_type=doc.trade_type,
            counterparty=doc.counterparty,
        )

    @property
    def store(self) -> VectorStore:
        """Direct access to the underlying vector store (for search)."""
        return self._store

    @property
    def embedder(self):
        """Direct access to the embedder (for embedding queries)."""
        return self._embedder

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _make_id(filename: str) -> str:
        """
        Generate a stable, deterministic doc_id from the filename.
        Same filename always produces the same ID (enables safe upsert).
        """
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, filename))


if __name__ == "__main__":
    pipeline = IngestionPipeline()
    report = pipeline.run(force=True)  # force=True to re-ingest in demo
