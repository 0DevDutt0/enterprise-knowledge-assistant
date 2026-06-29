# app/rag/retrieval/reranker.py
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.models.retrieval import RerankedResult, RetrievalResult

logger = logging.getLogger(__name__)


class Reranker(ABC):
    """Abstract base class for cross-encoder rerankers.

    Takes the top-K retrieval candidates and reorders them by relevance to the
    query using a more expensive but precise scoring model.
    """

    @abstractmethod
    def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int,
    ) -> list[RerankedResult]:
        """Score and reorder candidates; return at most top_k results."""


class BgeRerankerBase(Reranker):
    """Cross-encoder reranker backed by BAAI/bge-reranker-base.

    Scores each (query, passage) pair independently and returns candidates
    sorted by descending rerank score, trimmed to top_k.
    """

    def __init__(self, model_name: str, device: str) -> None:
        from sentence_transformers import CrossEncoder
        logger.info('reranker.load model=%s device=%s', model_name, device)
        self._model = CrossEncoder(model_name, device=device)

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int,
    ) -> list[RerankedResult]:
        """Score (query, chunk.text) pairs and return top_k sorted by score."""
        if not candidates:
            return []
        pairs = [(query, r.chunk.text) for r in candidates]
        raw_scores: list[float] = self._model.predict(pairs).tolist()

        scored = sorted(
            zip(raw_scores, candidates),
            key=lambda x: x[0],
            reverse=True,
        )
        return [
            RerankedResult(
                chunk=r.chunk,
                similarity_score=r.similarity_score,
                rerank_score=float(score),
            )
            for score, r in scored[:top_k]
        ]
