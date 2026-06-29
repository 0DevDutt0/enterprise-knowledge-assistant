# app/services/factory.py
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config.settings import Settings
from app.ingestion.pipeline import IngestionPipeline
from app.rag.generation.answer_assembler import AnswerAssembler
from app.rag.generation.llm_client import GroqClient
from app.rag.generation.pipeline import GenerationPipeline
from app.rag.generation.prompt_builder import PromptBuilder
from app.rag.retrieval.bm25_retriever import BM25Retriever
from app.rag.retrieval.embedder import BgeBaseEmbedder
from app.rag.retrieval.hybrid_retriever import HybridRetriever
from app.rag.retrieval.pipeline import RetrievalPipeline
from app.rag.retrieval.query_rewriter import LLMQueryRewriter, PassthroughRewriter, QueryRewriter
from app.rag.retrieval.reranker import BgeRerankerBase
from app.rag.retrieval.retriever import BaseRetriever, Retriever
from app.rag.retrieval.vector_store import FaissVectorStore
from app.services.health_service import HealthService
from app.services.indexing_service import IndexingService
from app.services.query_service import QueryService

logger = logging.getLogger(__name__)


@dataclass
class AppComponents:
    """Container for all wired service instances.

    Holds the three public services (query, indexing, health) plus the shared
    VectorStore so the FastAPI app can pass it to dependency injection without
    rebuilding objects per request.
    """

    query_service: QueryService
    indexing_service: IndexingService
    health_service: HealthService
    vector_store: FaissVectorStore


def create_app_components(settings: Settings) -> AppComponents:
    """Wire all concrete implementations into service objects.

    Loads the FAISS index from disk if it exists (graceful degradation
    otherwise). When retrieval_mode='hybrid', also loads or rebuilds the
    BM25 index. All heavy model loads happen here at startup, not per-request.

    Args:
        settings: Fully validated Settings instance.

    Returns:
        AppComponents with all services ready to serve requests.
    """
    logger.info('factory.create_app_components starting')

    embedder = BgeBaseEmbedder(
        model_name=settings.embedding_model,
        device=settings.device,
        batch_size=settings.embedding_batch_size,
    )
    reranker = BgeRerankerBase(
        model_name=settings.reranker_model,
        device=settings.device,
    )

    vector_store = FaissVectorStore()
    _try_load_index(vector_store, settings.vector_store_dir)

    llm_client = GroqClient(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        timeout=settings.groq_timeout_seconds,
        max_retries=settings.groq_max_retries,
    )

    # ------------------------------------------------------------------
    # Retrieval strategy: semantic (default) or hybrid (BM25 + FAISS)
    # ------------------------------------------------------------------
    semantic_retriever = Retriever(
        embedder=embedder,
        vector_store=vector_store,
        top_k=settings.top_k_retrieval,
    )

    bm25_retriever: BM25Retriever | None = None
    active_retriever: BaseRetriever

    if settings.retrieval_mode == 'hybrid':
        bm25_retriever = BM25Retriever()
        _try_load_bm25(bm25_retriever, vector_store, settings.vector_store_dir)
        active_retriever = HybridRetriever(
            semantic_retriever=semantic_retriever,
            bm25_retriever=bm25_retriever,
            top_k=settings.top_k_retrieval,
            rrf_k=settings.rrf_k,
        )
        logger.info('factory.retrieval mode=hybrid rrf_k=%d', settings.rrf_k)
    else:
        active_retriever = semantic_retriever
        logger.info('factory.retrieval mode=semantic')

    # ------------------------------------------------------------------
    # Query rewriter
    # ------------------------------------------------------------------
    rewriter: QueryRewriter = (
        LLMQueryRewriter(
            llm_client=llm_client,
            template_path=settings.query_rewrite_template_path,
        )
        if settings.query_rewriting_enabled
        else PassthroughRewriter()
    )
    logger.info('factory.query_rewriter type=%s', type(rewriter).__name__)

    retrieval_pipeline = RetrievalPipeline(
        retriever=active_retriever,
        reranker=reranker,
        top_k_rerank=settings.top_k_rerank,
        rewriter=rewriter,
    )

    prompt_builder = PromptBuilder(
        template_path=settings.prompt_template_path,
        max_context_chars=settings.max_context_chars,
        max_history_turns=settings.max_history_turns,
    )
    assembler = AnswerAssembler()
    generation_pipeline = GenerationPipeline(
        prompt_builder=prompt_builder,
        llm_client=llm_client,
        assembler=assembler,
        confidence_floor=settings.confidence_floor,
    )

    ingestion_pipeline = IngestionPipeline(settings=settings)

    query_service = QueryService(
        retrieval_pipeline=retrieval_pipeline,
        generation_pipeline=generation_pipeline,
    )
    indexing_service = IndexingService(
        ingestion_pipeline=ingestion_pipeline,
        embedder=embedder,
        vector_store=vector_store,
        raw_dir=settings.raw_dir,
        vector_store_dir=settings.vector_store_dir,
        bm25_retriever=bm25_retriever,
    )
    health_service = HealthService(
        llm_client=llm_client,
        vector_store=vector_store,
    )

    logger.info('factory.create_app_components done')
    return AppComponents(
        query_service=query_service,
        indexing_service=indexing_service,
        health_service=health_service,
        vector_store=vector_store,
    )


def _try_load_index(vector_store: FaissVectorStore, directory: str) -> None:
    """Attempt to load a persisted FAISS index; log a warning on failure."""
    try:
        vector_store.load(directory)
        logger.info('factory.index_loaded directory=%s size=%d', directory, vector_store.size)
    except Exception as exc:
        logger.warning(
            'factory.index_not_loaded directory=%s reason=%s', directory, exc
        )


def _try_load_bm25(
    bm25: BM25Retriever,
    vector_store: FaissVectorStore,
    directory: str,
) -> None:
    """Load BM25 index from disk, or build it from FAISS chunks if unavailable.

    Building from FAISS chunks avoids requiring a full rebuild when the server
    restarts after switching to hybrid mode for the first time.
    """
    try:
        bm25.load(directory)
        logger.info('factory.bm25_loaded directory=%s size=%d', directory, bm25.size)
        return
    except Exception as exc:
        logger.warning('factory.bm25_not_loaded reason=%s', exc)

    chunks = vector_store.chunks
    if chunks:
        logger.info('factory.bm25_building_from_faiss chunks=%d', len(chunks))
        bm25.index(chunks)
    else:
        logger.warning('factory.bm25_empty no FAISS chunks available to seed BM25')
