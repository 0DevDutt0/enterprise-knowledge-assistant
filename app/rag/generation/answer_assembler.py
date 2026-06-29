# app/rag/generation/answer_assembler.py
from __future__ import annotations

import logging
import math

from app.models.answer import Answer, ConfidenceBand, Citation
from app.models.retrieval import RerankedResult

logger = logging.getLogger(__name__)

CANONICAL_REFUSAL = 'I was unable to find relevant information in the indexed documents.'

_HIGH_THRESHOLD = 70.0
_MEDIUM_THRESHOLD = 40.0


def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid, maps any float to (0, 1)."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    exp_x = math.exp(x)
    return exp_x / (1.0 + exp_x)


class AnswerAssembler:
    """Turns an LLM response and retrieval metadata into a structured Answer.

    Confidence is computed as a weighted blend of sigmoid-normalised average
    rerank score (weight 0.6) and the top result's cosine similarity (weight
    0.4). Confidence bands map the [0, 100] percent to HIGH / MEDIUM / LOW.

    Citations are derived from the reranked results, not parsed from LLM text,
    so they are always accurate regardless of what the model says.
    """

    def assemble(
        self,
        llm_text: str,
        results: list[RerankedResult],
        processing_time_ms: float = 0.0,
    ) -> Answer:
        """Build an Answer from an LLM response and reranked results.

        Args:
            llm_text: Raw text returned by the LLM client.
            results: Reranked retrieval results that were used as context.
            processing_time_ms: End-to-end elapsed time in milliseconds.

        Returns:
            Fully populated Answer with citations and confidence.
        """
        text = llm_text.strip()
        if text == CANONICAL_REFUSAL:
            return self.make_refusal(processing_time_ms=processing_time_ms)

        confidence_percent, band = self._compute_confidence(results)
        citations = self._build_citations(results)
        logger.debug(
            'answer_assembler.assemble citations=%d confidence=%.1f band=%s',
            len(citations),
            confidence_percent,
            band.value,
        )
        return Answer(
            text=text,
            citations=citations,
            confidence_band=band,
            confidence_percent=confidence_percent,
            processing_time_ms=processing_time_ms,
            is_refusal=False,
        )

    def make_refusal(self, processing_time_ms: float = 0.0) -> Answer:
        """Return the canonical refusal Answer for low-confidence or empty results.

        Args:
            processing_time_ms: Elapsed time up to the refusal decision.

        Returns:
            Answer with is_refusal=True and the canonical refusal text.
        """
        return Answer(
            text=CANONICAL_REFUSAL,
            citations=[],
            confidence_band=ConfidenceBand.LOW,
            confidence_percent=0.0,
            processing_time_ms=processing_time_ms,
            is_refusal=True,
        )

    def _compute_confidence(
        self, results: list[RerankedResult]
    ) -> tuple[float, ConfidenceBand]:
        """Compute a [0, 100] confidence score and its band from reranked results.

        Uses sigmoid-normalised rerank scores (works for both raw CrossEncoder
        logits and the [0, 1] fake reranker used in tests).
        """
        if not results:
            return 0.0, ConfidenceBand.LOW

        sig_scores = [_sigmoid(r.rerank_score) for r in results]
        avg_sig = sum(sig_scores) / len(sig_scores)
        top_sim = results[0].similarity_score

        raw = 0.6 * avg_sig + 0.4 * top_sim
        confidence_percent = round(min(raw * 100.0, 100.0), 1)

        if confidence_percent >= _HIGH_THRESHOLD:
            band = ConfidenceBand.HIGH
        elif confidence_percent >= _MEDIUM_THRESHOLD:
            band = ConfidenceBand.MEDIUM
        else:
            band = ConfidenceBand.LOW

        return confidence_percent, band

    def _build_citations(self, results: list[RerankedResult]) -> list[Citation]:
        """Build Citation objects from reranked result metadata."""
        seen: set[str] = set()
        citations: list[Citation] = []
        for result in results:
            meta = result.chunk.metadata
            if meta.chunk_id in seen:
                continue
            seen.add(meta.chunk_id)
            citations.append(
                Citation(
                    document=meta.document,
                    page=meta.page,
                    section=meta.section,
                    chunk_id=meta.chunk_id,
                )
            )
        return citations
