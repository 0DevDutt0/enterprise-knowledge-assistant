# app/rag/retrieval/pipeline.py
from __future__ import annotations

import logging

from app.models.retrieval import RerankedResult
from app.rag.retrieval.query_rewriter import PassthroughRewriter, QueryRewriter
from app.rag.retrieval.reranker import Reranker
from app.rag.retrieval.retriever import BaseRetriever
from app.utils.text import clean_query

logger = logging.getLogger(__name__)


class RetrievalPipeline:
    """Orchestrates query cleaning, rewriting, retrieval, and reranking.

    Accepts any BaseRetriever implementation (Retriever for pure semantic
    search, HybridRetriever for BM25 + semantic fusion) so the pipeline
    is decoupled from the retrieval strategy.

    Public entry point:
        results = pipeline.run(query)  -> list[RerankedResult]
    """

    def __init__(
        self,
        retriever: BaseRetriever,
        reranker: Reranker,
        top_k_rerank: int,
        rewriter: QueryRewriter | None = None,
    ) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._top_k_rerank = top_k_rerank
        self._rewriter: QueryRewriter = rewriter if rewriter is not None else PassthroughRewriter()

    def run(self, query: str) -> list[RerankedResult]:
        """Clean, optionally rewrite, retrieve, and rerank for a user query.

        Args:
            query: Raw user query string.

        Returns:
            list[RerankedResult] sorted by rerank score descending, length <=
            top_k_rerank. Returns [] if the index is empty or the query is
            blank after cleaning.
        """
        cleaned = clean_query(query)
        if not cleaned:
            return []

        search_query = self._rewriter.rewrite(cleaned)

        candidates = self._retriever.retrieve(search_query)
        if not candidates:
            return []

        results = self._reranker.rerank(search_query, candidates, self._top_k_rerank)
        logger.debug(
            'retrieval_pipeline.run candidates=%d reranked=%d',
            len(candidates),
            len(results),
        )
        return results
