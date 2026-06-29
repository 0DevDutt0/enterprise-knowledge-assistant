# app/rag/retrieval/embedder.py
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class Embedder(ABC):
    """Abstract base class for text embedders.

    Concrete implementations wrap a specific model (local or API). The factory
    in app/services/ selects the implementation from Settings.
    """

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts and return a list of unit-normalized vectors."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string, applying any model-specific query prefix."""


class BgeBaseEmbedder(Embedder):
    """Local embedder backed by BAAI/bge-base-en-v1.5 via sentence-transformers.

    Vectors are L2-normalized so cosine similarity equals dot product and is
    compatible with FAISS IndexFlatIP.

    BGE retrieval models expect a prefix on queries but not on passages:
    "Represent this sentence: <query>"
    """

    _QUERY_PREFIX = 'Represent this sentence: '

    def __init__(self, model_name: str, device: str, batch_size: int = 32) -> None:
        from sentence_transformers import SentenceTransformer
        logger.info('embedder.load model=%s device=%s', model_name, device)
        self._model = SentenceTransformer(model_name, device=device)
        self._batch_size = batch_size

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed passages (no prefix). Returns normalized float vectors."""
        vecs = self._model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vecs.tolist()  # type: ignore[return-value]

    def embed_query(self, text: str) -> list[float]:
        """Embed a retrieval query with the BGE query prefix."""
        return self.embed([self._QUERY_PREFIX + text])[0]
