# app/rag/retrieval/vector_store.py
from __future__ import annotations

import logging
import os
import pickle
from abc import ABC, abstractmethod

import faiss
import numpy as np

from app.models.chunks import Chunk
from app.models.retrieval import RetrievalResult

logger = logging.getLogger(__name__)

_INDEX_FILE = 'index.faiss'
_CHUNKS_FILE = 'chunks.pkl'


class VectorStore(ABC):
    """Abstract base class for vector stores.

    Concrete implementations (FAISS, Qdrant, …) must implement all methods.
    The factory in app/services/ selects the implementation from Settings.
    """

    @abstractmethod
    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """Add chunks and their precomputed embeddings to the store."""

    @abstractmethod
    def search(self, query_embedding: list[float], top_k: int) -> list[RetrievalResult]:
        """Return the top_k most similar chunks for a query embedding."""

    @abstractmethod
    def persist(self, directory: str) -> None:
        """Persist the index and chunk metadata to disk."""

    @abstractmethod
    def load(self, directory: str) -> None:
        """Load a previously persisted index and chunk metadata from disk."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all vectors and chunk metadata from memory (does not delete disk files)."""

    @property
    @abstractmethod
    def size(self) -> int:
        """Number of vectors currently in the store."""


class FaissVectorStore(VectorStore):
    """FAISS-backed vector store using IndexFlatIP (cosine similarity).

    Assumes embeddings are L2-normalised so inner product equals cosine
    similarity. Chunks are stored in a parallel list indexed by FAISS row id.

    Persistence layout (one directory):
        index.faiss  - FAISS binary index
        chunks.pkl   - pickled list[Chunk] aligned with FAISS row ids
    """

    def __init__(self) -> None:
        self._index: faiss.IndexFlatIP | None = None
        self._chunks: list[Chunk] = []

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """Add chunks and their L2-normalised embedding vectors."""
        if not chunks:
            return
        vecs = np.array(embeddings, dtype='float32')
        if self._index is None:
            dim = vecs.shape[1]
            self._index = faiss.IndexFlatIP(dim)
            logger.debug('vector_store.created dim=%d', dim)
        self._index.add(vecs)
        self._chunks.extend(chunks)
        logger.debug('vector_store.add count=%d total=%d', len(chunks), self._index.ntotal)

    def clear(self) -> None:
        """Reset the in-memory index; does NOT delete persisted files."""
        self._index = None
        self._chunks = []
        logger.debug('vector_store.cleared')

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def search(self, query_embedding: list[float], top_k: int) -> list[RetrievalResult]:
        """Return up to top_k results sorted by cosine similarity (descending)."""
        if self._index is None or self._index.ntotal == 0:
            return []

        vec = np.array([query_embedding], dtype='float32')
        k = min(top_k, self._index.ntotal)
        distances, indices = self._index.search(vec, k)

        results: list[RetrievalResult] = []
        for dist, idx in zip(distances[0].tolist(), indices[0].tolist()):
            if idx < 0:
                continue
            score = float(max(0.0, min(1.0, dist)))  # clamp to [0, 1]
            results.append(RetrievalResult(chunk=self._chunks[idx], similarity_score=score))
        return results

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def persist(self, directory: str) -> None:
        """Write index.faiss and chunks.pkl to the given directory."""
        if self._index is None:
            logger.warning('vector_store.persist called on empty store; nothing written')
            return
        os.makedirs(directory, exist_ok=True)
        faiss.write_index(self._index, os.path.join(directory, _INDEX_FILE))
        with open(os.path.join(directory, _CHUNKS_FILE), 'wb') as fh:
            pickle.dump(self._chunks, fh)
        logger.info('vector_store.persisted directory=%s size=%d', directory, self._index.ntotal)

    def load(self, directory: str) -> None:
        """Load index.faiss and chunks.pkl from a previously persisted directory."""
        index_path = os.path.join(directory, _INDEX_FILE)
        chunks_path = os.path.join(directory, _CHUNKS_FILE)
        self._index = faiss.read_index(index_path)
        with open(chunks_path, 'rb') as fh:
            self._chunks = pickle.load(fh)
        logger.info('vector_store.loaded directory=%s size=%d', directory, self._index.ntotal)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        return self._index.ntotal if self._index is not None else 0

    @property
    def chunks(self) -> list[Chunk]:
        """Return a copy of all chunks currently held in the store.

        Used by the factory to populate a BM25 index from an already-loaded
        FAISS index without requiring a full rebuild.
        """
        return list(self._chunks)
