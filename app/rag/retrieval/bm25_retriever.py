# app/rag/retrieval/bm25_retriever.py
from __future__ import annotations

import logging
import os
import pickle

from app.models.chunks import Chunk
from app.models.retrieval import RetrievalResult

logger = logging.getLogger(__name__)

_BM25_FILE = 'bm25_index.pkl'


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase tokens for BM25 indexing."""
    return text.lower().split()


class BM25Retriever:
    """Keyword retrieval using BM25Okapi over indexed chunk texts.

    BM25 complements dense vector search by scoring exact and near-exact
    term matches (proper nouns, codes, IDs, rare domain terms) that may
    not map well into the embedding space.

    Usage:
        retriever = BM25Retriever()
        retriever.index(chunks)               # build from a list of Chunk
        results = retriever.search(query, 10) # list[RetrievalResult]
        retriever.persist(directory)          # save to disk
        retriever.load(directory)             # restore from disk
    """

    def __init__(self) -> None:
        self._bm25: object | None = None
        self._chunks: list[Chunk] = []

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index(self, chunks: list[Chunk]) -> None:
        """Build the BM25 index from scratch over the provided chunks.

        Replaces any previously indexed data.

        Args:
            chunks: Chunks to index; texts are lowercased and split on
                    whitespace for tokenisation.
        """
        from rank_bm25 import BM25Plus

        self._chunks = list(chunks)
        tokenised = [_tokenize(c.text) for c in chunks]
        # BM25Plus uses IDF = log((N+1)/df) which stays positive for any
        # corpus size, unlike BM25Okapi whose IDF collapses to 0 when a term
        # appears in exactly half the documents.
        self._bm25 = BM25Plus(tokenised)
        logger.info('bm25_retriever.indexed chunks=%d', len(chunks))

    def clear(self) -> None:
        """Reset the index; does NOT delete any persisted files."""
        self._bm25 = None
        self._chunks = []
        logger.debug('bm25_retriever.cleared')

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int) -> list[RetrievalResult]:
        """Return up to top_k chunks ranked by BM25 score.

        Args:
            query: Cleaned query string. Tokenised the same way as index
                   texts (lowercase split).
            top_k: Maximum number of results to return.

        Returns:
            list[RetrievalResult] sorted by BM25 score descending.
            Empty list if the index has not been built or is empty.
        """
        if self._bm25 is None or not self._chunks:
            return []

        tokens = _tokenize(query)
        scores: list[float] = self._bm25.get_scores(tokens).tolist()  # type: ignore[union-attr]

        pairs = sorted(
            enumerate(scores), key=lambda x: x[1], reverse=True
        )[:top_k]

        results: list[RetrievalResult] = []
        for idx, score in pairs:
            if score <= 0.0:
                continue
            results.append(
                RetrievalResult(
                    chunk=self._chunks[idx],
                    similarity_score=float(score),
                )
            )
        return results

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def persist(self, directory: str) -> None:
        """Pickle the BM25 index and chunk list to directory/bm25_index.pkl.

        Args:
            directory: Target directory (created if it does not exist).
        """
        if self._bm25 is None:
            logger.warning('bm25_retriever.persist called on empty index; nothing written')
            return
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, _BM25_FILE)
        with open(path, 'wb') as fh:
            pickle.dump({'bm25': self._bm25, 'chunks': self._chunks}, fh)
        logger.info('bm25_retriever.persisted directory=%s chunks=%d', directory, len(self._chunks))

    def load(self, directory: str) -> None:
        """Restore the BM25 index from directory/bm25_index.pkl.

        Args:
            directory: Directory containing a previously persisted index.

        Raises:
            FileNotFoundError: If the pickle file does not exist.
        """
        path = os.path.join(directory, _BM25_FILE)
        with open(path, 'rb') as fh:
            data = pickle.load(fh)
        self._bm25 = data['bm25']
        self._chunks = data['chunks']
        logger.info('bm25_retriever.loaded directory=%s chunks=%d', directory, len(self._chunks))

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        """Number of indexed chunks."""
        return len(self._chunks)
