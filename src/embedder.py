"""
embedder.py — Embedding model abstraction layer.

All embedding backends share the same interface:
    embedder = get_embedder()
    vector: list[float] = embedder.embed("some text")
    vectors: list[list[float]] = embedder.embed_batch(["text1", "text2"])

Switching backends only requires changing EMBEDDING_BACKEND in config.py.
No other code changes needed.
"""

import sys
import math
import re
from abc import ABC, abstractmethod
from collections import Counter
from pathlib import Path
from typing import Union

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import (
    EMBEDDING_BACKEND,
    SENTENCE_TRANSFORMER_MODEL,
    OPENAI_EMBEDDING_MODEL,
)


# ─── Abstract Base ────────────────────────────────────────────────────────

class BaseEmbedder(ABC):
    """Common interface for all embedding backends."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Embed a single string into a dense vector."""
        ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of strings. More efficient than calling embed() in a loop."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Dimensionality of the embedding vector."""
        ...

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Human-readable name of the backend."""
        ...

    def similarity(self, vec_a: list[float], vec_b: list[float]) -> float:
        """Cosine similarity between two vectors. Range: [-1, 1]."""
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# ─── Backend 1: TF-IDF (numpy, no external dependencies) ────────────────

class TFIDFEmbedder(BaseEmbedder):
    """
    TF-IDF based embedder using numpy only.

    How it works:
      - Builds a vocabulary from a corpus of documents
      - Represents each document as a TF-IDF weighted bag-of-words vector
      - Cosine similarity between vectors approximates semantic similarity

    Limitations vs sentence-transformers:
      - No semantic understanding (synonym-blind)
      - Vocabulary must be built before searching
      - Lower precision on short queries

    Sufficient for: development, offline testing, demo environments.
    """

    def __init__(self):
        self._vocab: dict[str, int] = {}         # word → index
        self._idf: list[float] = []              # IDF weights per vocab term
        self._corpus_size: int = 0
        self._fitted: bool = False

    # ── Vocabulary building ──────────────────────────────────────────────

    def fit(self, texts: list[str]) -> "TFIDFEmbedder":
        """
        Build vocabulary and IDF weights from a corpus.
        Must be called before embed() if using TF-IDF mode.
        """
        self._corpus_size = len(texts)
        tokenized = [self._tokenize(t) for t in texts]

        # Build vocabulary (all unique tokens)
        all_tokens = set(tok for doc in tokenized for tok in doc)
        self._vocab = {tok: i for i, tok in enumerate(sorted(all_tokens))}

        # Compute IDF: log((N + 1) / (df + 1)) + 1  (sklearn-style smooth IDF)
        df = Counter()
        for doc_tokens in tokenized:
            for tok in set(doc_tokens):
                df[tok] += 1

        n = self._corpus_size
        self._idf = [
            math.log((n + 1) / (df.get(tok, 0) + 1)) + 1
            for tok in sorted(self._vocab.keys())
        ]
        self._fitted = True
        return self

    def embed(self, text: str) -> list[float]:
        """Embed a single text. Fits on the single text if not yet fitted."""
        if not self._fitted:
            self.fit([text])
        return self._tfidf_vector(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Fit on the batch then embed all texts.
        If already fitted (from a prior ingest), just embed without re-fitting.
        """
        if not self._fitted:
            self.fit(texts)
        return [self._tfidf_vector(t) for t in texts]

    @property
    def dimension(self) -> int:
        return len(self._vocab)

    @property
    def backend_name(self) -> str:
        return "TF-IDF (numpy)"

    # ── Private helpers ──────────────────────────────────────────────────

    def _tokenize(self, text: str) -> list[str]:
        """Lowercase, strip punctuation, split on whitespace, remove stopwords."""
        STOPWORDS = {
            "a", "an", "the", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "as", "is", "are", "was",
            "were", "be", "been", "being", "have", "has", "had", "do", "does",
            "did", "will", "would", "could", "should", "may", "might", "shall",
            "per", "this", "that", "these", "those", "its", "it", "each",
        }
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        tokens = text.split()
        return [t for t in tokens if t not in STOPWORDS and len(t) > 1]

    def _tfidf_vector(self, text: str) -> list[float]:
        """Compute the TF-IDF vector for a single document."""
        tokens = self._tokenize(text)
        tf = Counter(tokens)
        total = len(tokens) or 1

        vec = [0.0] * len(self._vocab)
        for tok, idx in self._vocab.items():
            if tok in tf:
                term_freq = tf[tok] / total
                vec[idx] = term_freq * self._idf[idx]

        # L2 normalise
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


# ─── Backend 2: sentence-transformers ────────────────────────────────────

class SentenceTransformerEmbedder(BaseEmbedder):
    """
    Production embedding backend using sentence-transformers.

    Install: pip install sentence-transformers
    Default model: all-MiniLM-L6-v2 (384-dim, fast, strong for financial text)

    Recommended upgrade: all-mpnet-base-v2 (768-dim, higher precision)
    """

    def __init__(self, model_name: str = SENTENCE_TRANSFORMER_MODEL):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is not installed.\n"
                "Run: pip install sentence-transformers\n"
                "Or set EMBEDDING_BACKEND='tfidf' in config.py for offline use."
            )
        print(f"  Loading sentence-transformer model: {model_name} ...")
        self._model = SentenceTransformer(model_name)
        self._dim = self._model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> list[float]:
        return self._model.encode(text, normalize_embeddings=True).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(
            texts, normalize_embeddings=True, show_progress_bar=True
        ).tolist()

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def backend_name(self) -> str:
        return f"sentence-transformers ({SENTENCE_TRANSFORMER_MODEL})"


# ─── Backend 3: OpenAI ────────────────────────────────────────────────────

class OpenAIEmbedder(BaseEmbedder):
    """
    OpenAI embedding backend.

    Install: pip install openai
    Requires: OPENAI_API_KEY environment variable
    """

    _DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(self, model: str = OPENAI_EMBEDDING_MODEL):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai is not installed. Run: pip install openai")

        import os
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY environment variable not set.\n"
                "Export it before running: export OPENAI_API_KEY=sk-..."
            )
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._dim = self._DIMENSIONS.get(model, 1536)

    def embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(input=[text], model=self._model)
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(input=texts, model=self._model)
        return [item.embedding for item in response.data]

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def backend_name(self) -> str:
        return f"OpenAI ({self._model})"


# ─── Factory function ─────────────────────────────────────────────────────

def get_embedder(backend: str = EMBEDDING_BACKEND) -> BaseEmbedder:
    """
    Return the configured embedding backend.

    Args:
        backend: "tfidf" | "sentence-transformers" | "openai"
                 Defaults to EMBEDDING_BACKEND from config.py

    Returns:
        An initialised BaseEmbedder instance ready to use.
    """
    backend = backend.lower().strip()

    if backend == "tfidf":
        return TFIDFEmbedder()
    elif backend in ("sentence-transformers", "sentence_transformers", "st"):
        return SentenceTransformerEmbedder()
    elif backend == "openai":
        return OpenAIEmbedder()
    else:
        raise ValueError(
            f"Unknown embedding backend: {backend!r}. "
            "Choose from: 'tfidf', 'sentence-transformers', 'openai'"
        )


if __name__ == "__main__":
    print("\n🔢 Testing TF-IDF Embedder\n")
    embedder = get_embedder("tfidf")

    corpus = [
        "Interest Rate Swap SOFR fixed floating notional USD Goldman Sachs",
        "FX Forward foreign exchange EUR JPY counterparty settlement SWIFT",
        "Credit Default Swap CDS reference entity protection buyer seller",
    ]

    embedder.fit(corpus)
    vecs = embedder.embed_batch(corpus)
    print(f"  Vocab size:       {embedder.dimension}")
    print(f"  Vector[0][:5]:    {vecs[0][:5]}")

    query = "interest rate swap Goldman Sachs USD"
    q_vec = embedder.embed(query)

    print(f"\n  Query: '{query}'")
    for i, (text, vec) in enumerate(zip(corpus, vecs)):
        sim = embedder.similarity(q_vec, vec)
        print(f"  Doc {i}: similarity={sim:.4f} | {text[:60]}")
