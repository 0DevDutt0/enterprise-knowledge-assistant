# app/models/retrieval.py
from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.chunks import Chunk


class RetrievalResult(BaseModel, frozen=True):
    """A chunk returned by the retriever, with its retrieval score.

    similarity_score is non-negative; its range depends on the retriever:
    - FAISS cosine similarity: [0, 1]
    - BM25Plus: unbounded above (unnormalized term-frequency score)
    - RRF fusion: (0, 1) by construction (1/k sum)
    """

    chunk: Chunk
    similarity_score: float = Field(ge=0.0)


class RerankedResult(BaseModel, frozen=True):
    """A retrieval result after cross-encoder reranking.

    Both scores are preserved so AnswerAssembler can use both signals when
    computing the confidence band.
    """

    chunk: Chunk
    similarity_score: float = Field(ge=0.0)
    rerank_score: float
