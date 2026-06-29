# app/rag/generation/pipeline.py
from __future__ import annotations

import logging
import time

from app.models.answer import Answer
from app.models.conversation import ConversationTurn
from app.models.retrieval import RerankedResult
from app.rag.generation.answer_assembler import AnswerAssembler
from app.rag.generation.llm_client import LLMClient
from app.rag.generation.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class GenerationPipeline:
    """Orchestrates prompt construction, LLM completion, and answer assembly.

    Public entry point for the generation stage:
        answer = pipeline.run(query, reranked_results)

    The confidence floor short-circuit fires BEFORE the LLM is invoked.
    If the top reranked result's score is below the floor, the canonical
    refusal Answer is returned immediately without an API call.
    """

    def __init__(
        self,
        prompt_builder: PromptBuilder,
        llm_client: LLMClient,
        assembler: AnswerAssembler,
        confidence_floor: float,
    ) -> None:
        self._prompt_builder = prompt_builder
        self._llm_client = llm_client
        self._assembler = assembler
        self._confidence_floor = confidence_floor

    def run(
        self,
        query: str,
        results: list[RerankedResult],
        history: list[ConversationTurn] | None = None,
    ) -> Answer:
        """Generate a grounded Answer for a query given reranked retrieval results.

        Args:
            query: Cleaned user query string.
            results: Reranked retrieval results from RetrievalPipeline.run().
            history: Prior conversation turns for context injection into the prompt.

        Returns:
            Answer with text, citations, confidence, and processing time.
            If results are empty or top score is below the confidence floor,
            returns the canonical refusal Answer without invoking the LLM.
        """
        start = time.monotonic()

        if not results or results[0].rerank_score < self._confidence_floor:
            elapsed_ms = (time.monotonic() - start) * 1000.0
            logger.info(
                'generation_pipeline.refusal top_score=%s floor=%s',
                results[0].rerank_score if results else 'none',
                self._confidence_floor,
            )
            return self._assembler.make_refusal(processing_time_ms=elapsed_ms)

        prompt = self._prompt_builder.build(query, results, history)
        llm_text = self._llm_client.complete(prompt)

        elapsed_ms = (time.monotonic() - start) * 1000.0
        answer = self._assembler.assemble(
            llm_text=llm_text,
            results=results,
            processing_time_ms=elapsed_ms,
        )
        logger.info(
            'generation_pipeline.complete band=%s confidence=%.1f elapsed_ms=%.1f',
            answer.confidence_band.value,
            answer.confidence_percent,
            elapsed_ms,
        )
        return answer
