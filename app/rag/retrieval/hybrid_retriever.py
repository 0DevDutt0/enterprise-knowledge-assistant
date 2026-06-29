# app/rag/retrieval/hybrid_retriever.py
from __future__ import annotations

import logging

from app.models.chunks import Chunk
from app.models.retrieval import RetrievalResult
from app.rag.retrieval.bm25_retriever import BM25Retriever
from app.rag.retrieval.retriever import BaseRetriever, Retriever

logger = logging.getLogger(__name__)


class HybridRetriever(BaseRetriever):
    """Fuses dense semantic retrieval (FAISS) and sparse keyword retrieval (BM25).

    Uses Reciprocal Rank Fusion (RRF) to combine ranked lists from both
    retrievers without requiring score normalisation. Each result receives
    a fused score:

        score(result) = sum over each list of  1 / (rrf_k + rank)

    where rank is the 1-based position in that list (results absent from a
    list contribute 0). Results are deduplicated by chunk_id and sorted by
    fused score descending.

    Args:
        semantic_retriever: Dense FAISS-backed Retriever instance.
        bm25_retriever: Sparse BM25Retriever instance.
        top_k: Number of candidates to fetch from each individual retriever.
               The fused output may contain up to 2 * top_k unique results
               (when the two lists share no overlap).
        rrf_k: RRF constant controlling rank impact. Default 60 is standard;
               increase to reduce the advantage of top-ranked results.
    """

    def __init__(
        self,
        semantic_retriever: Retriever,
        bm25_retriever: BM25Retriever,
        top_k: int,
        rrf_k: int = 60,
    ) -> None:
        self._semantic = semantic_retriever
        self._bm25 = bm25_retriever
        self._top_k = top_k
        self._rrf_k = rrf_k

    def retrieve(self, query: str) -> list[RetrievalResult]:
        """Retrieve and fuse results from both retrievers.

        Args:
            query: Cleaned (and optionally rewritten) query string.

        Returns:
            RRF-fused list[RetrievalResult] sorted by fused score descending.
            Empty list if both sub-retrievers return nothing.
        """
        semantic_results = self._semantic.retrieve(query)
        bm25_results = self._bm25.search(query, self._top_k)

        fused = _reciprocal_rank_fusion(
            [semantic_results, bm25_results],
            rrf_k=self._rrf_k,
        )
        logger.debug(
            'hybrid_retriever.retrieve semantic=%d bm25=%d fused=%d',
            len(semantic_results),
            len(bm25_results),
            len(fused),
        )
        return fused


def _reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievalResult]],
    rrf_k: int,
) -> list[RetrievalResult]:
    """Combine multiple ranked result lists via Reciprocal Rank Fusion.

    Args:
        ranked_lists: Each inner list is a ranking (best first) from one
                      retriever.
        rrf_k: RRF constant k (typically 60).

    Returns:
        Deduplicated list[RetrievalResult] sorted by RRF score descending.
        The RetrievalResult.similarity_score field contains the RRF score.
    """
    scores: dict[str, float] = {}
    chunks: dict[str, Chunk] = {}

    for ranked_list in ranked_lists:
        for rank, result in enumerate(ranked_list, start=1):
            cid = result.chunk.metadata.chunk_id
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + rank)
            chunks[cid] = result.chunk

    sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    return [
        RetrievalResult(chunk=chunks[cid], similarity_score=round(scores[cid], 6))
        for cid in sorted_ids
    ]
