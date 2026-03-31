"""
vector_store.py — Vector store abstraction layer.

Two backends:
  - JSONVectorStore:   Stores embeddings in a local JSON file. No extra deps.
                       Perfect for development and testing.
  - ChromaVectorStore: Persistent ChromaDB store. Recommended for production.
                       Install: pip install chromadb

Both backends implement the same VectorStore interface.
Switching is a one-line change in config.py.
"""

import sys
import json
import math
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import (
    VECTOR_STORE_DIR,
    VECTOR_STORE_BACKEND,
    CHROMA_COLLECTION_NAME,
    DEFAULT_TOP_K,
    MIN_SIMILARITY_SCORE,
)


# ─── Result Model ─────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    """A single search result returned by the vector store."""
    doc_id: str
    filename: str
    score: float                        # Cosine similarity [0, 1]
    metadata: dict = field(default_factory=dict)
    snippet: str = ""                   # First 300 chars of document text

    def __repr__(self):
        return (
            f"SearchResult(score={self.score:.3f}, "
            f"filename={self.filename!r}, "
            f"trade_type={self.metadata.get('trade_type')!r})"
        )


# ─── Abstract Base ────────────────────────────────────────────────────────

class VectorStore(ABC):

    @abstractmethod
    def add(
        self,
        doc_id: str,
        vector: list[float],
        metadata: dict,
        text: str,
    ) -> None:
        """Store a single document embedding with its metadata and raw text."""
        ...

    @abstractmethod
    def search(
        self,
        query_vector: list[float],
        top_k: int = DEFAULT_TOP_K,
        filters: Optional[dict] = None,
    ) -> list[SearchResult]:
        """
        Find the top_k most similar documents to query_vector.

        Args:
            query_vector: Dense embedding of the search query.
            top_k:        Number of results to return.
            filters:      Optional metadata filters, e.g.
                          {"trade_type": "Interest Rate Swap", "jurisdiction": "US"}
                          All filter conditions must match (AND logic).

        Returns:
            List of SearchResult sorted by descending similarity score.
        """
        ...

    @abstractmethod
    def delete(self, doc_id: str) -> bool:
        """Remove a document from the store. Returns True if deleted."""
        ...

    @abstractmethod
    def count(self) -> int:
        """Return the number of documents in the store."""
        ...

    @abstractmethod
    def list_all(self) -> list[dict]:
        """Return metadata for all stored documents (no vectors)."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Remove all documents from the store."""
        ...


# ─── Backend 1: JSON (dev/offline) ───────────────────────────────────────

class JSONVectorStore(VectorStore):
    """
    File-backed vector store using JSON.

    Storage format:
        {
          "<doc_id>": {
            "vector":   [0.1, 0.2, ...],
            "metadata": { "trade_type": "...", ... },
            "text":     "Full document text ...",
            "snippet":  "First 300 chars..."
          },
          ...
        }

    Similarity search: brute-force cosine similarity over all stored vectors.
    Suitable for corpora up to ~10,000 documents.
    For larger corpora, migrate to ChromaDB or Pinecone.
    """

    def __init__(self, store_path: Optional[Path] = None):
        self._path = Path(store_path or VECTOR_STORE_DIR / "store.json")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict = self._load()

    # ── Core operations ──────────────────────────────────────────────────

    def add(self, doc_id: str, vector: list[float], metadata: dict, text: str) -> None:
        self._data[doc_id] = {
            "vector":   vector,
            "metadata": metadata,
            "text":     text,
            "snippet":  text[:300].replace("\n", " "),
        }
        self._save()

    def search(
        self,
        query_vector: list[float],
        top_k: int = DEFAULT_TOP_K,
        filters: Optional[dict] = None,
    ) -> list[SearchResult]:
        scored = []
        for doc_id, entry in self._data.items():
            # Apply metadata filters (AND logic)
            if filters and not self._matches_filters(entry["metadata"], filters):
                continue

            score = self._cosine_similarity(query_vector, entry["vector"])
            if score >= MIN_SIMILARITY_SCORE:
                scored.append(
                    SearchResult(
                        doc_id=doc_id,
                        filename=entry["metadata"].get("filename", doc_id),
                        score=round(score, 4),
                        metadata=entry["metadata"],
                        snippet=entry.get("snippet", ""),
                    )
                )

        # Sort by descending score, return top_k
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]

    def delete(self, doc_id: str) -> bool:
        if doc_id in self._data:
            del self._data[doc_id]
            self._save()
            return True
        return False

    def count(self) -> int:
        return len(self._data)

    def list_all(self) -> list[dict]:
        return [
            {"doc_id": doc_id, **entry["metadata"]}
            for doc_id, entry in self._data.items()
        ]

    def clear(self) -> None:
        self._data = {}
        self._save()

    # ── Private helpers ──────────────────────────────────────────────────

    def _load(self) -> dict:
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        if len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _matches_filters(metadata: dict, filters: dict) -> bool:
        for key, value in filters.items():
            if metadata.get(key, "").lower() != str(value).lower():
                return False
        return True


# ─── Backend 2: ChromaDB (production) ────────────────────────────────────

class ChromaVectorStore(VectorStore):
    """
    Persistent ChromaDB vector store.

    Install: pip install chromadb
    Data persists across runs in VECTOR_STORE_DIR.

    ChromaDB uses HNSW index for fast approximate nearest-neighbour search,
    making it suitable for 100k+ documents.
    """

    def __init__(self, collection_name: str = CHROMA_COLLECTION_NAME):
        try:
            import chromadb
        except ImportError:
            raise ImportError(
                "chromadb is not installed.\n"
                "Run: pip install chromadb\n"
                "Or set VECTOR_STORE_BACKEND='json' in config.py for offline use."
            )

        self._client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, doc_id: str, vector: list[float], metadata: dict, text: str) -> None:
        # ChromaDB requires string values in metadata
        clean_meta = {k: str(v) for k, v in metadata.items()}
        self._collection.upsert(
            ids=[doc_id],
            embeddings=[vector],
            metadatas=[clean_meta],
            documents=[text[:1000]],  # ChromaDB stores document snippet
        )

    def search(
        self,
        query_vector: list[float],
        top_k: int = DEFAULT_TOP_K,
        filters: Optional[dict] = None,
    ) -> list[SearchResult]:
        where = None
        if filters:
            # ChromaDB uses its own filter syntax
            if len(filters) == 1:
                key, val = next(iter(filters.items()))
                where = {key: {"$eq": str(val)}}
            else:
                where = {"$and": [{k: {"$eq": str(v)}} for k, v in filters.items()]}

        results = self._collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, self._collection.count()),
            where=where,
            include=["metadatas", "distances", "documents"],
        )

        search_results = []
        for i in range(len(results["ids"][0])):
            # ChromaDB returns L2 distance for cosine space; convert to similarity
            distance = results["distances"][0][i]
            score = max(0.0, 1.0 - distance)

            if score >= MIN_SIMILARITY_SCORE:
                meta = results["metadatas"][0][i]
                search_results.append(SearchResult(
                    doc_id=results["ids"][0][i],
                    filename=meta.get("filename", "unknown"),
                    score=round(score, 4),
                    metadata=meta,
                    snippet=results["documents"][0][i][:300],
                ))

        return sorted(search_results, key=lambda r: r.score, reverse=True)

    def delete(self, doc_id: str) -> bool:
        try:
            self._collection.delete(ids=[doc_id])
            return True
        except Exception:
            return False

    def count(self) -> int:
        return self._collection.count()

    def list_all(self) -> list[dict]:
        result = self._collection.get(include=["metadatas"])
        return [
            {"doc_id": id_, **meta}
            for id_, meta in zip(result["ids"], result["metadatas"])
        ]

    def clear(self) -> None:
        all_ids = self._collection.get()["ids"]
        if all_ids:
            self._collection.delete(ids=all_ids)


# ─── Factory ──────────────────────────────────────────────────────────────

def get_vector_store(backend: str = VECTOR_STORE_BACKEND) -> VectorStore:
    """
    Return the configured vector store backend.

    Args:
        backend: "json" (dev) | "chroma" (production)

    Returns:
        An initialised VectorStore ready to use.
    """
    backend = backend.lower().strip()
    if backend == "json":
        return JSONVectorStore()
    elif backend in ("chroma", "chromadb"):
        return ChromaVectorStore()
    else:
        raise ValueError(
            f"Unknown vector store backend: {backend!r}. "
            "Choose from: 'json', 'chroma'"
        )


if __name__ == "__main__":
    print("\n🗃  Testing JSONVectorStore\n")
    store = JSONVectorStore(store_path=Path("/tmp/test_store.json"))
    store.clear()

    # Add some fake vectors
    import random
    for i, name in enumerate(["IRS_Goldman", "FX_JPM", "CDS_Barclays"]):
        vec = [random.uniform(-1, 1) for _ in range(50)]
        norm = math.sqrt(sum(v*v for v in vec))
        vec = [v/norm for v in vec]
        store.add(
            doc_id=f"doc_{i}",
            vector=vec,
            metadata={"filename": f"{name}.docx", "trade_type": name},
            text=f"Sample text for {name}",
        )

    print(f"  Stored: {store.count()} documents")
    print(f"  List: {[d['filename'] for d in store.list_all()]}")

    query_vec = [random.uniform(-1, 1) for _ in range(50)]
    results = store.search(query_vec, top_k=3)
    print(f"\n  Search results (random query):")
    for r in results:
        print(f"    {r.filename}: score={r.score:.4f}")
