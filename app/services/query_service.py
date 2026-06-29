# app/services/query_service.py
from __future__ import annotations

import logging

from app.models.answer import Answer
from app.models.conversation import ConversationTurn
from app.rag.generation.pipeline import GenerationPipeline
from app.rag.retrieval.pipeline import RetrievalPipeline

logger = logging.getLogger(__name__)


class QueryService:
    """Facade over the retrieval and generation pipelines.

    The single public method ask() is the entry point for answering a user
    question end-to-end: retrieve candidate chunks, rerank, generate a cited
    answer, and return a fully populated Answer object.
    """

    def __init__(
        self,
        retrieval_pipeline: RetrievalPipeline,
        generation_pipeline: GenerationPipeline,
    ) -> None:
        self._retrieval = retrieval_pipeline
        self._generation = generation_pipeline

    def ask(
        self,
        query: str,
        history: list[ConversationTurn] | None = None,
    ) -> Answer:
        """Answer a user question using the indexed knowledge base.

        Args:
            query: Raw user question string (cleaning is handled downstream).
            history: Prior conversation turns (oldest first). Injected into
                     the generation prompt so the LLM can resolve follow-up
                     references. Only non-refusal turns should be passed.

        Returns:
            Answer with text, citations, confidence band, and processing time.
            Returns the canonical refusal Answer if retrieval finds no relevant
            content or the top result falls below the confidence floor.
        """
        logger.info(
            'query_service.ask query_len=%d history_turns=%d',
            len(query),
            len(history) if history else 0,
        )
        results = self._retrieval.run(query)
        answer = self._generation.run(query, results, history)
        logger.info(
            'query_service.ask done band=%s refusal=%s',
            answer.confidence_band.value,
            answer.is_refusal,
        )
        return answer
