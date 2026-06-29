# app/services/indexing_service.py
from __future__ import annotations

import logging
import os
import time

from app.ingestion.pipeline import IngestionPipeline
from app.models.chunks import Chunk
from app.rag.retrieval.bm25_retriever import BM25Retriever
from app.rag.retrieval.embedder import Embedder
from app.rag.retrieval.vector_store import VectorStore
from app.services.models import IndexStats

logger = logging.getLogger(__name__)


class IndexingService:
    """Rebuilds the FAISS vector index (and optionally the BM25 index) from
    all PDFs in raw_dir.

    Calling rebuild() is idempotent: it clears both stores before processing,
    so repeated calls produce the same result regardless of prior state.
    """

    def __init__(
        self,
        ingestion_pipeline: IngestionPipeline,
        embedder: Embedder,
        vector_store: VectorStore,
        raw_dir: str,
        vector_store_dir: str,
        bm25_retriever: BM25Retriever | None = None,
    ) -> None:
        self._ingestion = ingestion_pipeline
        self._embedder = embedder
        self._store = vector_store
        self._raw_dir = raw_dir
        self._vector_store_dir = vector_store_dir
        self._bm25 = bm25_retriever

    def rebuild(self) -> IndexStats:
        """Clear and rebuild the vector index from all PDFs in raw_dir.

        When a BM25Retriever is injected, the keyword index is rebuilt from
        the same chunks and persisted alongside the FAISS index.

        Returns:
            IndexStats with total chunk count, list of indexed document IDs,
            and elapsed time in milliseconds.
        """
        start = time.monotonic()
        self._store.clear()
        if self._bm25 is not None:
            self._bm25.clear()

        pdf_paths = self._find_pdfs()
        if not pdf_paths:
            logger.warning('indexing_service.rebuild no PDFs found in %s', self._raw_dir)

        documents: list[str] = []
        total_chunks = 0
        all_chunks: list[Chunk] = []

        for pdf_path in pdf_paths:
            doc_id = os.path.basename(pdf_path)
            logger.info('indexing_service.rebuild processing %s', doc_id)
            try:
                chunks = self._ingestion.run(pdf_path)
                if not chunks:
                    logger.warning('indexing_service.rebuild no chunks from %s', doc_id)
                    continue
                texts = [c.text for c in chunks]
                embeddings = self._embedder.embed(texts)
                self._store.add(chunks, embeddings)
                all_chunks.extend(chunks)
                documents.append(doc_id)
                total_chunks += len(chunks)
                logger.info(
                    'indexing_service.rebuild doc=%s chunks=%d', doc_id, len(chunks)
                )
            except Exception as exc:
                logger.error(
                    'indexing_service.rebuild error doc=%s error=%s', doc_id, exc
                )

        self._store.persist(self._vector_store_dir)

        if self._bm25 is not None and all_chunks:
            self._bm25.index(all_chunks)
            self._bm25.persist(self._vector_store_dir)
            logger.info('indexing_service.rebuild bm25 indexed chunks=%d', len(all_chunks))

        elapsed_ms = (time.monotonic() - start) * 1000.0

        logger.info(
            'indexing_service.rebuild done docs=%d chunks=%d elapsed_ms=%.1f',
            len(documents),
            total_chunks,
            elapsed_ms,
        )
        return IndexStats(
            total_chunks=total_chunks,
            documents=documents,
            elapsed_ms=elapsed_ms,
        )

    def _find_pdfs(self) -> list[str]:
        """Return sorted list of .pdf paths in raw_dir."""
        if not os.path.isdir(self._raw_dir):
            return []
        return sorted(
            os.path.join(self._raw_dir, f)
            for f in os.listdir(self._raw_dir)
            if f.lower().endswith('.pdf')
        )
