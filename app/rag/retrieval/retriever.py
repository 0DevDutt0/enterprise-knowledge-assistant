# app/rag/retrieval/retriever.py
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.models.retrieval import RetrievalResult
from app.rag.retrieval.embedder import Embedder
from app.rag.retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)


class BaseRetriever(ABC):
    """Abstract interface for all retriever implementations.

    Concrete classes (Retriever, HybridRetriever) implement retrieve() so
    that RetrievalPipeline can accept either without knowing the internals.
    """

    @abstractmethod
    def retrieve(self, query: str) -> list[RetrievalResult]:
        """Return ranked candidate chunks for the given query.

        Args:
            query: Cleaned (and optionally rewritten) query string.

        Returns:
            list[RetrievalResult] sorted by relevance score descending.
        """


class Retriever(BaseRetriever):
    """Composes an Embedder and a VectorStore to retrieve candidate chunks.

    This class is intentionally thin: it embeds the cleaned query and delegates
    the similarity search to the VectorStore.
    """

    def __init__(self, embedder: Embedder, vector_store: VectorStore, top_k: int) -> None:
        self._embedder = embedder
        self._store = vector_store
        self._top_k = top_k

    def retrieve(self, query: str) -> list[RetrievalResult]:
        """Embed query and return up to top_k candidates from the vector store.

        Args:
            query: Already-cleaned query string (control chars stripped,
                   whitespace normalised by the caller).

        Returns:
            list[RetrievalResult] sorted by similarity score descending.
        """
        embedding = self._embedder.embed_query(query)
        results = self._store.search(embedding, self._top_k)
        logger.debug('retriever.search query_len=%d results=%d', len(query), len(results))
        return results
